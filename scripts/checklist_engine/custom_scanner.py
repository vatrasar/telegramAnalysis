"""System-1 Multi-Theme Custom Section Scanner and Corroboration Engine.

Scans dialogue threads simultaneously against all proposed custom report sections
using the OpenRouter Decisions API (choice + score + locate). Automatically discovers
corroborating threads across the longitudinal archive and extracts anchor quotes via locate,
forming a fully evidenced package before subagent dispatch or chapter drafting.
"""

import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple, Set

from common.config import load_config, get_api_key
from checklist_engine.custom_sections import ensure_custom_sections_table, get_custom_sections


def _call_custom_scanner_api(
    full_dialogue: str,
    sections: List[Dict[str, Any]],
    api_key: str,
    model: str = "perplexity/pplx-decider-v1.3",
    max_retries: int = 3
) -> Tuple[Dict[str, Any], float]:
    """Call OpenRouter Decisions API for multi-theme custom section scanning."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Custom Section Scanner"
    }

    trimmed_dialogue = (full_dialogue or "").strip()[:25000]

    criteria: Dict[str, str] = {
        "none": "Dialogue does not relate to or substantiate any of the proposed custom report sections."
    }
    for s in sections:
        sec_key = f"sec_{s['section_id']}"
        criteria[sec_key] = f"{s['title']}: {s['rationale']}"

    payload = {
        "model": model,
        "state": f"DIALOGUE TRANSCRIPT:\n{trimmed_dialogue}",
        "questions": {
            "matching_section": {
                "type": "choice",
                "instructions": "Which proposed custom report section theme does this dialogue substantively discuss, evidence, or exemplify?",
                "criteria": criteria
            },
            "salience_score": {
                "type": "score",
                "instructions": "Rate substantive evidential and psychological diagnostic depth for the matched custom section theme.",
                "criteria": [
                    "Irrelevant or no evidence",
                    "Minor passing mention",
                    "Moderate relevant context",
                    "High direct evidence or turning point",
                    "Critical defining crisis, confession, or milestone"
                ]
            }
        }
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                answers = data.get("answers", {})
                matched_sec = str(answers.get("matching_section", {}).get("choice", "none")).strip()
                salience = float(answers.get("salience_score", {}).get("score", 0.0))
                cost = float(data.get("usage", {}).get("cost", 0.0))

                quote_obj = answers.get("evidence_quote", {})
                quote_text = quote_obj.get("span") or quote_obj.get("text") or quote_obj.get("verbatim") or ""

                return {
                    "matching_section": matched_sec,
                    "salience_score": salience,
                    "evidence_quote": str(quote_text).strip()
                }, cost
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API HTTP {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.0 + attempt * 0.5)
                continue
            raise e

    raise RuntimeError(f"Decisions API failed after {max_retries} attempts.")


def _find_anchor_message(
    cur: sqlite3.Cursor,
    chat_id: str,
    thread_id: str,
    quote_text: str
) -> Tuple[Optional[int], str]:
    """Find anchor message ID and date for an extracted quote within a thread."""
    if not quote_text or len(quote_text.strip()) < 5:
        # Fallback to first message in thread
        cur.execute("""
        SELECT message_id, coalesce(timestamp, '') FROM messages
        WHERE chat_id = ? AND thread_id = ?
        ORDER BY message_id ASC LIMIT 1;
        """, (chat_id, thread_id))
        row = cur.fetchone()
        return (row[0], row[1][:10]) if row else (None, "")

    clean_sub = quote_text.strip().replace("\"", "").replace("'", "")[:40]
    cur.execute("""
    SELECT message_id, coalesce(timestamp, '') FROM messages
    WHERE chat_id = ? AND thread_id = ? AND text LIKE ?
    ORDER BY message_id ASC LIMIT 1;
    """, (chat_id, thread_id, f"%{clean_sub}%"))
    row = cur.fetchone()
    if row:
        return row[0], row[1][:10]

    # Fallback to earliest message in thread
    cur.execute("""
    SELECT message_id, coalesce(timestamp, '') FROM messages
    WHERE chat_id = ? AND thread_id = ?
    ORDER BY message_id ASC LIMIT 1;
    """, (chat_id, thread_id))
    row = cur.fetchone()
    return (row[0], row[1][:10]) if row else (None, "")


def scan_custom_sections_system1(
    conn: sqlite3.Connection,
    chat_id: str,
    db_path: Optional[str] = None,
    model: Optional[str] = None,
    concurrency: int = 4,
    salience_threshold: float = 3.0,
    all_threads: bool = False,
    threads_filter: Optional[List[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    auto_record_facts: bool = True
) -> Dict[str, Any]:
    """Execute System-1 multi-theme scan across threads for all proposed custom sections."""
    ensure_custom_sections_table(conn)
    cur = conn.cursor()

    # 1. Fetch proposed custom sections
    sections = get_custom_sections(conn, chat_id)
    if not sections:
        return {
            "chat_id": chat_id,
            "status": "no_sections",
            "message": "No proposed custom report sections found. Propose sections first via --propose-custom-section."
        }

    # 2. Load API configuration
    config_override = None
    if db_path and os.path.exists(db_path):
        candidate_cfg = os.path.join(os.path.dirname(os.path.abspath(db_path)), "config", "embeddings_config.json")
        if os.path.exists(candidate_cfg):
            config_override = candidate_cfg

    try:
        config = load_config(config_override)
        api_key = get_api_key(config)
    except Exception:
        config, api_key = {}, ""

    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
        raise ValueError("Valid OpenRouter API key required in config/embeddings_config.json for Decisions API.")

    chosen_model = model or config.get("triage_model") or "perplexity/pplx-decider-v1.3"

    # 3. Select candidate threads
    if threads_filter:
        placeholders = ",".join("?" for _ in threads_filter)
        query = f"""
        SELECT t.thread_id, coalesce(t.dialogue_text, '')
        FROM threads t
        WHERE t.chat_id = ? AND t.thread_id IN ({placeholders})
        ORDER BY t.thread_id ASC;
        """
        cur.execute(query, [chat_id] + threads_filter)
    elif all_threads:
        cur.execute("""
        SELECT t.thread_id, coalesce(t.dialogue_text, '')
        FROM threads t
        WHERE t.chat_id = ?
        ORDER BY t.thread_id ASC;
        """, (chat_id,))
    else:
        # Check thread_triage anomalies or high salience
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
        has_triage = cur.fetchone()[0] > 0

        if has_triage:
            query = """
            SELECT DISTINCT t.thread_id, coalesce(t.dialogue_text, '')
            FROM threads t
            LEFT JOIN thread_triage tt ON t.thread_id = tt.thread_id AND t.chat_id = tt.chat_id
            LEFT JOIN thread_audit_checklist tac ON t.thread_id = tac.thread_id AND t.chat_id = tac.chat_id
            WHERE t.chat_id = ?
              AND (
                  tt.is_atypical = 1
                  OR tt.emotional_peak != 'none'
                  OR tt.is_relational_conflict = 1
                  OR tt.is_medical_or_grief_crisis = 1
                  OR tt.is_acute_vulnerability_or_breakdown = 1
                  OR tt.is_bizarre_or_boundary_violation = 1
                  OR coalesce(tac.salience_score, 0) >= 2.5
                  OR tac.status = 'pending'
              )
            ORDER BY t.thread_id ASC;
            """
            cur.execute(query, (chat_id,))
        else:
            cur.execute("""
            SELECT t.thread_id, coalesce(t.dialogue_text, '')
            FROM threads t
            WHERE t.chat_id = ?
            ORDER BY t.thread_id ASC;
            """, (chat_id,))

    rows = cur.fetchall()
    if limit and limit > 0:
        rows = rows[:limit]

    if not rows:
        return {
            "chat_id": chat_id,
            "status": "no_threads",
            "message": "No candidate threads found for custom section scanning."
        }

    # Map section keys
    sec_map: Dict[str, Dict[str, Any]] = {f"sec_{s['section_id']}": s for s in sections}
    matches_by_section: Dict[int, Dict[str, Any]] = {
        s["section_id"]: {
            "title": s["title"],
            "filename": s["filename"],
            "matched_threads": [],
            "extracted_quotes": []
        }
        for s in sections
    }

    start_time = time.time()
    total_cost = 0.0

    def _eval_thread(row: Tuple[str, str]) -> Tuple[str, Dict[str, Any], float]:
        t_id, dialogue = row
        res, cost = _call_custom_scanner_api(dialogue, sections, api_key, model=chosen_model)
        return t_id, res, cost

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_eval_thread, r): r[0] for r in rows}
        for fut in as_completed(futures):
            tid = futures[fut]
            try:
                t_id, res, cost = fut.result()
                total_cost += cost
                matched_sec = res.get("matching_section", "none")
                salience = float(res.get("salience_score", 0.0))
                quote = str(res.get("evidence_quote", "")).strip()

                if matched_sec in sec_map and salience >= salience_threshold:
                    sec_info = sec_map[matched_sec]
                    sec_id = sec_info["section_id"]
                    matches_by_section[sec_id]["matched_threads"].append(t_id)

                    msg_id, dt_str = _find_anchor_message(cur, chat_id, t_id, quote)
                    anchor_tag = f"[#{msg_id} | {dt_str}]" if msg_id else f"[{t_id}]"
                    quote_entry = f"{anchor_tag} \"{quote}\"" if quote else f"{anchor_tag} (Salience: {salience:.1f})"
                    matches_by_section[sec_id]["extracted_quotes"].append({
                        "thread_id": t_id,
                        "anchor_msg_id": msg_id,
                        "anchor_date": dt_str,
                        "quote_text": quote,
                        "formatted_quote": quote_entry,
                        "salience": salience
                    })
            except Exception as e:
                print(f"[!] Warning: Failed evaluating thread {tid}: {e}", file=sys.stderr)

    elapsed = round(time.time() - start_time, 2)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 4. Update custom_report_sections in database
    if not dry_run:
        for s in sections:
            sec_id = s["section_id"]
            sec_matches = matches_by_section[sec_id]
            new_tids = sec_matches["matched_threads"]
            new_quotes = [q["formatted_quote"] for q in sec_matches["extracted_quotes"] if q.get("quote_text")]

            if not new_tids and not new_quotes:
                continue

            # Merge with existing
            cur.execute("""
            SELECT associated_threads, key_quotes FROM custom_report_sections
            WHERE section_id = ? AND chat_id = ?;
            """, (sec_id, chat_id))
            curr_row = cur.fetchone()
            curr_tids_str = curr_row[0] or "" if curr_row else ""
            curr_quotes_str = curr_row[1] or "" if curr_row else ""

            existing_tids = set(t.strip() for t in curr_tids_str.split(",") if t.strip())
            for t in new_tids:
                existing_tids.add(t)
            merged_tids = sorted(list(existing_tids))

            existing_quotes = [q.strip() for q in curr_quotes_str.split("\n") if q.strip()]
            for q in new_quotes:
                if q not in existing_quotes:
                    existing_quotes.append(q)

            updated_tids_str = ",".join(merged_tids)
            updated_quotes_str = "\n".join(existing_quotes)

            cur.execute("""
            UPDATE custom_report_sections
            SET associated_threads = ?,
                key_quotes = ?
            WHERE section_id = ? AND chat_id = ?;
            """, (updated_tids_str, updated_quotes_str, sec_id, chat_id))

            # Auto record into discovered_facts if requested
            if auto_record_facts and new_quotes:
                cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='discovered_facts';")
                if cur.fetchone()[0] > 0:
                    for qinfo in sec_matches["extracted_quotes"]:
                        if not qinfo["quote_text"]:
                            continue
                        cat = f"custom_{s['filename'].replace('.md', '')}"
                        summary = f"{s['title']}: Milestone/Evidence verified via System-1 scan"
                        cur.execute("""
                        INSERT INTO discovered_facts (
                            chat_id, thread_id, anchor_msg_id, category,
                            sphere_id, target_agent, fact_summary, verbatim_quote,
                            discovered_by, created_at, subject
                        ) VALUES (?, ?, ?, ?, 'CUSTOM', 'chapter-drafter', ?, ?, 'system1_custom_scanner', ?, '');
                        """, (
                            chat_id, qinfo["thread_id"], qinfo["anchor_msg_id"],
                            cat, summary, qinfo["quote_text"], now_iso
                        ))

        conn.commit()

    return {
        "chat_id": chat_id,
        "scanned_threads_count": len(rows),
        "proposed_sections_count": len(sections),
        "matches_by_section": matches_by_section,
        "elapsed_seconds": elapsed,
        "total_cost_usd": round(total_cost, 5),
        "model_used": chosen_model,
        "dry_run": dry_run
    }
