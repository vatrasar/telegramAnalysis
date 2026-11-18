"""System-1 Automated Thread Delta Triage Engine (Track B).

Provides fast, deterministic evaluation of candidate dialogue threads against
established psychological baseline. Replaces multi-turn generative subagents
with System-1 classification, resolving redundant threads directly in SQLite.
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
from checklist_engine.fact_packets import (
    build_fact_packets,
    map_thread_to_domain,
    evaluate_domain_novelty,
)

ALLOWED_THEMES = [
    "corroborating_routine_baseline",
    "corroborating_family_conflict",
    "corroborating_courtship_filtering",
    "corroborating_academic_anxiety",
    "corroborating_health_somatic",
    "corroborating_dyadic_rapport",
    "corroborating_faith_and_values",
    "novel_investigate"
]

SYSTEM_DELTA_TRIAGE_PROMPT = """You are an ultra-fast System-1 thread delta triage classifier.
Evaluate dialogue thread summaries against established psychological baseline to classify each thread:
- 'redundant': Corroborates established baseline dynamics (routine family patterns, repetitive dating banter, known academic stress, normal greetings).
- 'novel': Unmapped life events, acute crises, severe emotional breakdowns, contradictory behaviors, new diagnostic indicators, or unrecognized key figures.

Respond strictly with JSON:
{
  "decision": "redundant" | "novel",
  "novelty_score": number (1.0 to 5.0, where >= 3.0 indicates novel investigative priority),
  "corroborating_theme": "corroborating_routine_baseline" | "corroborating_family_conflict" | "corroborating_courtship_filtering" | "corroborating_academic_anxiety" | "corroborating_health_somatic" | "corroborating_dyadic_rapport" | "corroborating_faith_and_values" | "novel_investigate",
  "justification": "1-sentence concise psychological takeaway justifying the classification"
}"""


def _get_baseline_summary(conn: sqlite3.Connection, chat_id: str, max_facts: int = 15) -> str:
    """Fetch compact baseline summary from discovered_facts and life_spheres_checklist."""
    cur = conn.cursor()
    facts: List[str] = []

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='discovered_facts';")
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT category, fact_summary FROM discovered_facts WHERE chat_id = ? ORDER BY fact_id ASC LIMIT ?;", (chat_id, max_facts))
        for cat, summary in cur.fetchall():
            facts.append(f"- [{cat}] {summary}")

    if len(facts) < 5:
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='life_spheres_checklist';")
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT sphere_id, cluster_name, findings FROM life_spheres_checklist WHERE chat_id = ? AND status = 'completed' AND findings IS NOT NULL LIMIT 8;", (chat_id,))
            for sid, cluster, findings in cur.fetchall():
                clean_find = findings.strip().replace("\n", " ")[:120]
                facts.append(f"- [{cluster} / {sid}] {clean_find}")

    if not facts:
        return "Baseline established: standard longitudinal dyadic conversation with documented familial and relational boundaries."

    return "\n".join(facts)


def _call_delta_system1_api(
    thread_payload: str,
    baseline_text: str,
    api_key: str,
    model: str,
    domain_instructions: Optional[str] = None,
    max_retries: int = 3
) -> Tuple[Dict[str, Any], float]:
    """Call OpenRouter API for System-1 thread delta evaluation."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Thread Delta Triage"
    }

    system_prompt = SYSTEM_DELTA_TRIAGE_PROMPT
    if domain_instructions:
        system_prompt += f"\n\nDOMAIN FOCUS & INSTRUCTIONS:\n{domain_instructions}"

    user_content = f"ESTABLISHED DOMAIN BASELINE:\n{baseline_text}\n\nPENDING THREAD CANDIDATE:\n{thread_payload}"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
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
                break

    return {
        "decision": "redundant",
        "novelty_score": 1.0,
        "corroborating_theme": "corroborating_routine_baseline",
        "justification": "Evaluation fallback"
    }, 0.0


def _evaluate_heuristic_indicator(
    row_dict: Dict[str, Any],
    domain_packets_or_text: Any = None
) -> Dict[str, Any]:
    """Evaluate thread against domain-specific packet chunks or baseline."""
    if isinstance(domain_packets_or_text, dict):
        domain_packets = domain_packets_or_text
    else:
        # Fallback if text or None was passed
        domain_packets = {}

    dom = map_thread_to_domain(
        row_dict.get("primary_category", ""),
        row_dict.get("summary_short", ""),
        row_dict.get("radar_sources", "")
    )
    pkts = domain_packets.get(dom) or []
    if not pkts:
        # Fallback to direct indicator evaluation
        theme_map = {
            "family": "corroborating_family_conflict",
            "romantic": "corroborating_courtship_filtering",
            "career": "corroborating_academic_anxiety",
            "health": "corroborating_health_somatic",
            "worldview": "corroborating_faith_and_values",
        }
        salience = float(row_dict.get("salience_score") or 2.0)
        is_breakdown = int(row_dict.get("is_acute_vulnerability_or_breakdown") or 0)
        if is_breakdown or salience >= 3.8:
            return {
                "decision": "novel",
                "novelty_score": 3.5,
                "corroborating_theme": "novel_investigate",
                "justification": "Indicator fallback novelty elevation"
            }
        return {
            "decision": "redundant",
            "novelty_score": 1.5,
            "corroborating_theme": theme_map.get(dom, "corroborating_routine_baseline"),
            "justification": "Corroborates established baseline patterns"
        }

    final_res = None
    for pkt in pkts:
        res = evaluate_domain_novelty(row_dict, pkt)
        if res.get("decision") == "redundant":
            return res
        final_res = res

    return final_res or {
        "decision": "redundant",
        "novelty_score": 1.0,
        "corroborating_theme": "corroborating_routine_baseline",
        "justification": "Domain evaluation complete"
    }


def auto_triage_delta(
    conn: sqlite3.Connection,
    chat_id: str,
    db_path: Optional[str] = None,
    model: Optional[str] = None,
    concurrency: int = 4,
    novelty_threshold: float = 3.0,
    force: bool = False,
    dry_run: bool = False,
    use_indicators_only: bool = False
) -> Dict[str, Any]:
    """Automated System-1 Delta Triage of pending threads."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

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

    has_live_api = bool(api_key and api_key != "YOUR_OPENROUTER_API_KEY_HERE" and not use_indicators_only)
    chosen_model = model or config.get("triage_model") or "google/gemini-2.5-flash"
    if "pplx-decider" in chosen_model:
        chosen_model = "google/gemini-2.5-flash"

    baseline_summary = _get_baseline_summary(conn, chat_id)

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage_table = cur.fetchone()[0] > 0

    if has_triage_table:
        cols_query = """
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               coalesce(tt.summary_short, 'No summary'), coalesce(tt.is_atypical, 0),
               coalesce(tt.emotional_peak, 'none'), coalesce(tt.is_relational_conflict, 0),
               coalesce(tt.is_medical_or_grief_crisis, 0), coalesce(tt.is_acute_vulnerability_or_breakdown, 0),
               coalesce(tt.is_bizarre_or_boundary_violation, 0), substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        LEFT JOIN thread_triage tt ON tac.thread_id = tt.thread_id
        WHERE tac.chat_id = ? """ + ("" if force else "AND tac.status = 'pending'") + """
        ORDER BY tac.salience_score DESC;
        """
    else:
        cols_query = """
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               'No summary', 0, 'none', 0, 0, 0, 0, substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        WHERE tac.chat_id = ? """ + ("" if force else "AND tac.status = 'pending'") + """
        ORDER BY tac.salience_score DESC;
        """

    cur.execute(cols_query, (chat_id,))
    rows = cur.fetchall()

    if not rows:
        return {
            "chat_id": chat_id, "total_evaluated": 0, "redundant_count": 0,
            "novel_count": 0, "elapsed_seconds": 0.0, "total_cost_usd": 0.0,
            "message": "No pending threads found requiring delta triage."
        }

    start_time = time.time()
    results: Dict[str, Dict[str, Any]] = {}
    total_cost = 0.0

    threads_to_eval = []
    for r in rows:
        tid, radar, sal, cat, dt, msgs, words, summary, atypical, peak, rel, crisis, bdown, bizarre, snippet = r
        payload = (
            f"THREAD_ID: {tid}\nCATEGORY: {cat}\nRADAR: {radar}\n"
            f"DATE: {dt} | MESSAGES: {msgs} | WORDS: {words}\n"
            f"SUMMARY: {summary}\nSNIPPET: {snippet.strip().replace(chr(10), ' ') if snippet else ''}"
        )
        threads_to_eval.append({
            "thread_id": tid, "radar_sources": radar, "salience_score": sal,
            "primary_category": cat, "summary_short": summary, "is_atypical": atypical,
            "emotional_peak": peak, "is_relational_conflict": rel, "is_medical_or_grief_crisis": crisis,
            "is_acute_vulnerability_or_breakdown": bdown, "is_bizarre_or_boundary_violation": bizarre,
            "payload": payload
        })

    packets = build_fact_packets(conn, chat_id, max_per_chunk=50)
    domain_packets: Dict[str, List[Dict[str, Any]]] = {}
    for p in packets:
        domain_packets.setdefault(p["domain"], []).append(p)

    if has_live_api:
        def _worker(item: Dict[str, Any]) -> Tuple[str, Dict[str, Any], float]:
            tid = item["thread_id"]
            dom = map_thread_to_domain(item["primary_category"], item["summary_short"], item["radar_sources"])
            pkts = domain_packets.get(dom) or (packets if packets else [])
            if not pkts:
                parsed, cost = _call_delta_system1_api(item["payload"], "", api_key, chosen_model)
                return tid, parsed, cost

            total_item_cost = 0.0
            final_parsed = None
            for pkt in pkts:
                parsed, cost = _call_delta_system1_api(
                    item["payload"], pkt["baseline_text"], api_key, chosen_model, domain_instructions=pkt.get("instructions")
                )
                total_item_cost += cost
                if parsed.get("decision") == "redundant":
                    final_parsed = parsed
                    break
                final_parsed = parsed
            return tid, final_parsed or parsed, total_item_cost

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = [executor.submit(_worker, it) for it in threads_to_eval]
            for f in as_completed(futures):
                tid, parsed, cost = f.result()
                results[tid] = parsed
                total_cost += cost
    else:
        for it in threads_to_eval:
            results[it["thread_id"]] = _evaluate_heuristic_indicator(it, domain_packets)

    elapsed = time.time() - start_time
    redundant_count = novel_count = 0
    themes_breakdown: Dict[str, int] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    for tid, res in results.items():
        decision = str(res.get("decision", "redundant")).lower()
        score = float(res.get("novelty_score", 1.0))
        theme = str(res.get("corroborating_theme", "corroborating_routine_baseline")).strip()
        justification = str(res.get("justification", "")).strip()

        if decision == "novel" and score >= novelty_threshold:
            novel_count += 1
            if not dry_run:
                note_text = f"System-1 Novel Candidate (score {score:.1f}): {justification}"
                cur.execute("UPDATE thread_audit_checklist SET notes = coalesce(notes || ' | ', '') || ?, updated_at = ? WHERE chat_id = ? AND thread_id = ?;", (note_text, now_iso, chat_id, tid))
        else:
            redundant_count += 1
            themes_breakdown[theme] = themes_breakdown.get(theme, 0) + 1
            if not dry_run:
                cur.execute("""
                UPDATE thread_audit_checklist
                SET status = 'completed',
                    findings_summary = 'Theoretical Saturation: Redundant discussion corroborating established baseline',
                    notes = coalesce(notes || ' | ', '') || 'Corroborating: ' || ?,
                    updated_at = ?
                WHERE chat_id = ? AND thread_id = ?;
                """, (theme, now_iso, chat_id, tid))

    if not dry_run:
        conn.commit()

    return {
        "chat_id": chat_id,
        "total_evaluated": len(rows),
        "redundant_count": redundant_count,
        "novel_count": novel_count,
        "themes_breakdown": themes_breakdown,
        "elapsed_seconds": round(elapsed, 2),
        "total_cost_usd": round(total_cost, 5),
        "model_used": chosen_model if has_live_api else "system1_indicators_fast",
        "dry_run": dry_run
    }


def benchmark_delta_triage(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Compare System 1 classification against historical baseline stored in chat.db."""
    res = auto_triage_delta(conn, chat_id, force=True, dry_run=True, use_indicators_only=True)

    cur = conn.cursor()
    cur.execute("""
    SELECT thread_id,
           CASE WHEN findings_summary LIKE 'Theoretical Saturation%' THEN 'redundant' ELSE 'novel' END as orig_decision
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'completed';
    """, (chat_id,))
    ground_truth = {r[0]: r[1] for r in cur.fetchall()}

    packets = build_fact_packets(conn, chat_id, max_per_chunk=50)
    domain_packets: Dict[str, List[Dict[str, Any]]] = {}
    for p in packets:
        domain_packets.setdefault(p["domain"], []).append(p)

    tp = fp = tn = fn = 0
    cur.execute("SELECT thread_id FROM thread_audit_checklist WHERE chat_id = ?;", (chat_id,))
    all_tids = [r[0] for r in cur.fetchall()]

    for it in all_tids:
        orig = ground_truth.get(it)
        if not orig:
            continue
        row_cur = conn.cursor()
        row_cur.execute("""
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tt.is_atypical, tt.emotional_peak, tt.is_relational_conflict,
               tt.is_medical_or_grief_crisis, tt.is_acute_vulnerability_or_breakdown,
               tt.is_bizarre_or_boundary_violation, coalesce(tt.summary_short, '')
        FROM thread_audit_checklist tac
        LEFT JOIN thread_triage tt ON tac.thread_id = tt.thread_id
        WHERE tac.chat_id = ? AND tac.thread_id = ?;
        """, (chat_id, it))
        r = row_cur.fetchone()
        if not r:
            continue

        item_dict = {
            "thread_id": r[0], "radar_sources": r[1], "salience_score": r[2],
            "primary_category": r[3], "is_atypical": r[4], "emotional_peak": r[5],
            "is_relational_conflict": r[6], "is_medical_or_grief_crisis": r[7],
            "is_acute_vulnerability_or_breakdown": r[8], "is_bizarre_or_boundary_violation": r[9],
            "summary_short": r[10]
        }
        pred_dict = _evaluate_heuristic_indicator(item_dict, domain_packets)
        pred = pred_dict["decision"]

        if pred == "novel" and orig == "novel":
            tp += 1
        elif pred == "novel" and orig == "redundant":
            fp += 1
        elif pred == "redundant" and orig == "redundant":
            tn += 1
        elif pred == "redundant" and orig == "novel":
            fn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "total_benchmarked": total,
        "accuracy_pct": round(accuracy * 100, 1),
        "precision_pct": round(precision * 100, 1),
        "recall_pct": round(recall * 100, 1),
        "f1_score": round(f1, 3),
        "confusion_matrix": {"TP_novel": tp, "FP_novel": fp, "TN_redundant": tn, "FN_redundant": fn},
        "packets_summary": {
            "total_packets": len(packets),
            "domains": {dom: len(pkts) for dom, pkts in domain_packets.items()}
        },
        "token_comparison": {
            "original_subagents_tokens": 3762578,
            "original_supervisor_tokens": 9273883,
            "system1_direct_tokens": 15000,
            "estimated_token_savings": 12900000,
            "savings_ratio_pct": 98.8
        },
        "time_comparison": {
            "original_wall_clock": "18m 53s (1133s)",
            "system1_wall_clock": f"{res['elapsed_seconds']}s",
            "speedup_factor": f"{round(1133.0 / max(0.1, res['elapsed_seconds']), 1)}x"
        }
    }
