"""
System-1 Automated Evidence Triage & Batch Routing Engine.

Provides ultra-fast, deterministic triage and chapter allocation for audited dialogue
evidence items using System-1 models (OpenRouter Decisions API / structured completions).
Eliminates intermediate scripting and LLM context degradation by persisting allocations
directly to the SQLite database (chat.db).
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
from typing import Dict, Any, List, Optional, Tuple

from common.config import load_config, get_api_key
from checklist_engine.threads_db import ensure_thread_checklist_table

ALLOWED_CHAPTERS = [
    "family",
    "career",
    "worldview",
    "romantic",
    "lifestyle",
    "attachment",
    "playbook_tactics",
    "creed_quirks",
    "reliability_defenses",
    "discard_noise"
]

SYSTEM_TRIAGE_PROMPT = """You are an ultra-fast System-1 psychological evidence classifier.
Your task is to classify extracted dialogue evidence for a comprehensive personality profile.
Evaluate whether each evidence item contains substantive, diagnostically valuable evidence about the primary subject,
or should be discarded (e.g. routine logistical chitchat, filler, or personal biographical disclosures of the interlocutor only).

If valuable, assign it to the most relevant report chapter from the allowed list:
- 'romantic': Romantic relationships, courtship, suitors, dating apps, ex-partners.
- 'family': Family dynamics, parental authority, sibling relationships, birth order/filial expectations.
- 'attachment': Attachment style, abandonment fears, rejection sensitivity, boundary porosity/selectivity.
- 'playbook_tactics': Communication friction, red buttons, triggers, de-escalation, manipulation defenses.
- 'reliability_defenses': Psychological defenses, rationalization, suppression, denial, emotional decompensation.
- 'creed_quirks': Deep personal creed, idiosyncrasies, specific habits, non-religious ethical codes.
- 'worldview': Religious orthodoxy, halal/haram, moral fatalism, political or cultural worldview.
- 'lifestyle': Daily habits, studies/thesis, healthcare work, sleep patterns, somatic symptoms.
- 'career': Professional trajectory, work accomplishments, vocational conflicts.
- 'discard_noise': Interlocutor-only personal monologues, trivial chitchat, or zero psychological relevance.

Respond strictly with a JSON object:
{
  "is_valuable_subject_evidence": boolean,
  "salience_score": number (1.0 to 5.0),
  "target_chapter": "family" | "career" | "worldview" | "romantic" | "lifestyle" | "attachment" | "playbook_tactics" | "creed_quirks" | "reliability_defenses" | "discard_noise",
  "significance": "1-sentence concise psychological takeaway justifying chapter allocation or discard reason"
}"""


def _call_system1_api(
    item_payload: str,
    api_key: str,
    model: str,
    max_retries: int = 3
) -> Tuple[Dict[str, Any], float]:
    """Call OpenRouter Chat Completions endpoint with JSON schema constraint."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Evidence Triage"
    }

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_TRIAGE_PROMPT},
            {"role": "user", "content": item_payload}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    req_data = json.dumps(body).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                parsed = json.loads(content)
                cost = float(data.get("usage", {}).get("cost", 0.0))
                return parsed, cost
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1.0 + attempt * 0.5)
            else:
                return {
                    "is_valuable_subject_evidence": False,
                    "salience_score": 1.0,
                    "target_chapter": "discard_noise",
                    "significance": "API call failure after retries"
                }, 0.0

    return {
        "is_valuable_subject_evidence": False,
        "salience_score": 1.0,
        "target_chapter": "discard_noise",
        "significance": "Unknown evaluation failure"
    }, 0.0


def auto_triage_evidence(
    conn: sqlite3.Connection,
    chat_id: str,
    db_path: Optional[str] = None,
    model: Optional[str] = None,
    concurrency: int = 4,
    salience_threshold: float = 2.5,
    force: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Automatically evaluate and route audited evidence items using System 1.
    Persists allocations directly into thread_audit_checklist in SQLite.
    """
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    config_override = None
    if db_path and os.path.exists(db_path):
        candidate_cfg = os.path.join(os.path.dirname(os.path.abspath(db_path)), "config", "embeddings_config.json")
        if os.path.exists(candidate_cfg):
            config_override = candidate_cfg

    config = load_config(config_override)
    api_key = get_api_key(config)
    if not api_key or api_key == "YOUR_OPENROUTER_API_KEY_HERE":
        raise ValueError("Missing or unconfigured OpenRouter API key in config/embeddings_config.json")

    raw_model = model or config.get("triage_model") or "google/gemini-2.5-flash"
    if raw_model.startswith("~"):
        raw_model = raw_model.lstrip("~")
    # Ensure a viable model is selected if pplx-decider is specified but unavailable
    if "pplx-decider" in raw_model:
        chosen_model = "google/gemini-2.5-flash"
    else:
        chosen_model = raw_model

    # Select completed threads needing triage
    if force:
        query = """
        SELECT thread_id, primary_category, findings_summary, key_quotes, thematic_tags, notes
        FROM thread_audit_checklist
        WHERE chat_id = ? AND status = 'completed';
        """
        cur.execute(query, (chat_id,))
    else:
        query = """
        SELECT thread_id, primary_category, findings_summary, key_quotes, thematic_tags, notes
        FROM thread_audit_checklist
        WHERE chat_id = ? AND status = 'completed'
          AND (target_chapter IS NULL OR target_chapter = '');
        """
        cur.execute(query, (chat_id,))

    rows = cur.fetchall()
    if not rows:
        return {
            "chat_id": chat_id,
            "total_evaluated": 0,
            "routed_count": 0,
            "discarded_count": 0,
            "elapsed_seconds": 0.0,
            "total_cost_usd": 0.0,
            "message": "No pending completed evidence items found requiring triage."
        }

    items_to_eval = []
    for r in rows:
        tid, cat, findings, quotes, tags, notes = r
        payload = f"THREAD_ID: {tid}\nCATEGORY: {cat or ''}\nTAGS: {tags or ''}\nFINDINGS: {findings or ''}\nQUOTES: {quotes or ''}"
        items_to_eval.append({
            "thread_id": tid,
            "payload": payload,
            "existing_notes": notes or ""
        })

    start_time = time.time()
    results = {}
    total_cost = 0.0

    def _worker(entry: Dict[str, Any]) -> Tuple[str, Dict[str, Any], float, str]:
        tid = entry["thread_id"]
        parsed, cost = _call_system1_api(entry["payload"], api_key, chosen_model)
        return tid, parsed, cost, entry["existing_notes"]

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [executor.submit(_worker, it) for it in items_to_eval]
        for f in as_completed(futures):
            tid, parsed, cost, notes = f.result()
            results[tid] = (parsed, notes)
            total_cost += cost

    elapsed = time.time() - start_time

    # Persist allocations in SQLite
    routed_count = 0
    discarded_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    chapter_breakdown: Dict[str, int] = {}

    if not dry_run:
        update_sql = """
        UPDATE thread_audit_checklist
        SET target_agent = ?, target_chapter = ?, notes = ?, updated_at = ?
        WHERE chat_id = ? AND thread_id = ?;
        """
        updates = []
        for tid, (parsed, existing_notes) in results.items():
            is_valuable = bool(parsed.get("is_valuable_subject_evidence", False))
            score = float(parsed.get("salience_score", 1.0))
            raw_ch = str(parsed.get("target_chapter", "discard_noise")).strip().lower()
            sig = str(parsed.get("significance", "")).strip()

            target_chapter = raw_ch if raw_ch in ALLOWED_CHAPTERS else "discard_noise"

            if is_valuable and target_chapter != "discard_noise" and score >= salience_threshold:
                target_agent = "chapter-drafter"
                note_addition = f"Significance: {sig}"
                new_notes = f"{existing_notes} | {note_addition}".strip(" | ") if existing_notes else note_addition
                routed_count += 1
                chapter_breakdown[target_chapter] = chapter_breakdown.get(target_chapter, 0) + 1
            else:
                target_agent = ""
                target_chapter = "discarded"
                note_addition = f"System-1 Discarded (salience {score:.1f}): {sig}"
                new_notes = f"{existing_notes} | {note_addition}".strip(" | ") if existing_notes else note_addition
                discarded_count += 1

            updates.append((target_agent, target_chapter, new_notes, now_iso, chat_id, tid))

        cur.executemany(update_sql, updates)
        conn.commit()
    else:
        for tid, (parsed, _) in results.items():
            is_valuable = bool(parsed.get("is_valuable_subject_evidence", False))
            score = float(parsed.get("salience_score", 1.0))
            ch = str(parsed.get("target_chapter", "discard_noise")).strip().lower()
            if is_valuable and ch != "discard_noise" and score >= salience_threshold:
                routed_count += 1
                chapter_breakdown[ch] = chapter_breakdown.get(ch, 0) + 1
            else:
                discarded_count += 1

    return {
        "chat_id": chat_id,
        "total_evaluated": len(rows),
        "routed_count": routed_count,
        "discarded_count": discarded_count,
        "chapter_breakdown": chapter_breakdown,
        "elapsed_seconds": round(elapsed, 2),
        "total_cost_usd": round(total_cost, 5),
        "model": chosen_model,
        "dry_run": dry_run
    }


def batch_route_evidence(
    conn: sqlite3.Connection,
    chat_id: str,
    batch_input: str
) -> Dict[str, Any]:
    """
    Ingest and apply batch routing definitions from a JSON file path or raw JSON string.
    Expected format: list of dicts with:
    [{"thread_id": "...", "target_chapter": "...", "target_agent": "...", "significance": "..."}]
    """
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    raw_data = None
    if os.path.exists(batch_input):
        with open(batch_input, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        try:
            raw_data = json.loads(batch_input)
        except Exception as e:
            raise ValueError(f"Could not parse --batch-route as valid JSON or existing file: {e}")

    if not isinstance(raw_data, list):
        raise ValueError("Batch routing input must be a JSON list of routing objects or tuples.")

    now_iso = datetime.now(timezone.utc).isoformat()
    success_count = 0
    chapter_breakdown: Dict[str, int] = {}

    update_sql = """
    UPDATE thread_audit_checklist
    SET target_agent = ?, target_chapter = ?, notes = coalesce(notes || ' | ', '') || ?, updated_at = ?
    WHERE chat_id = ? AND thread_id = ?;
    """
    updates = []

    for item in raw_data:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            tid = str(item[0]).strip()
            agent = str(item[1]).strip()
            chapter = str(item[2]).strip().lower()
            sig = str(item[3]).strip() if len(item) > 3 else ""
        elif isinstance(item, dict):
            tid = str(item.get("thread_id", "")).strip()
            agent = str(item.get("target_agent", "chapter-drafter")).strip()
            chapter = str(item.get("target_chapter", "")).strip().lower()
            sig = str(item.get("significance", item.get("rationale", ""))).strip()
        else:
            continue

        if not tid or not chapter:
            continue

        note_str = f"Significance: {sig}" if sig else "Batch routed"
        updates.append((agent, chapter, note_str, now_iso, chat_id, tid))
        chapter_breakdown[chapter] = chapter_breakdown.get(chapter, 0) + 1
        success_count += 1

    if updates:
        cur.executemany(update_sql, updates)
        conn.commit()

    return {
        "chat_id": chat_id,
        "total_routed": success_count,
        "chapter_breakdown": chapter_breakdown,
        "success": True
    }
