"""High-level batch pipelines for triage screening and Scaledown enrichment."""

import os
import sys
import time
import json
import sqlite3
import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.config import load_config
from triage_engine.schema import init_triage_table
from triage_engine.deciders import evaluate_single_thread
from triage_engine.scaledown_client import call_openrouter_summary, call_openrouter_extraction
from triage_engine.reporting import print_reduction_report


def run_triage(
    db_path: str,
    limit: Optional[int] = None,
    force: bool = False,
    concurrency_override: Optional[int] = None,
    threshold_override: Optional[float] = None,
    model_override: Optional[str] = None,
    chat_id: Optional[str] = None
) -> int:
    """Execute triage process across database threads."""
    config = load_config()
    api_key = str(config.get("api_key", "")).strip()

    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key or api_key.startswith("YOUR_"):
        print("[ERROR] Valid OpenRouter API key required in config/embeddings_config.json!")
        print("  -> Please edit config/embeddings_config.json and set your OpenRouter API key.")
        return 2

    model = model_override or str(config.get("triage_model", "perplexity/pplx-decider-v1.2")).strip()
    concurrency = concurrency_override or int(config.get("concurrency", 4))
    salience_threshold = threshold_override if threshold_override is not None else float(config.get("salience_threshold", 2.0))

    conn = sqlite3.connect(db_path)
    init_triage_table(conn)
    cur = conn.cursor()

    sql = "SELECT thread_id, chat_id, start_date, duration_seconds, message_count, participants, initiator, dialogue_text FROM threads"
    where_clauses = []
    params = []

    if not force:
        where_clauses.append("thread_id NOT IN (SELECT thread_id FROM thread_triage)")
    if chat_id:
        where_clauses.append("chat_id = ?")
        params.append(chat_id)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY start_timestamp ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("[*] All threads in database have already been triaged! (Use --force to re-evaluate).")
        print_reduction_report(conn)
        conn.close()
        return 0

    thread_items = []
    for r in rows:
        thread_items.append({
            "thread_id": r[0],
            "chat_id": r[1],
            "start_date": r[2],
            "duration_seconds": r[3],
            "message_count": r[4],
            "participants": r[5],
            "initiator": r[6],
            "dialogue_text": r[7]
        })

    total_to_process = len(thread_items)
    print(f"[*] Starting System-1 Triage on {total_to_process} threads:")
    print("    - Provider:    OpenRouter")
    print(f"    - Model:       {model}")
    print(f"    - Concurrency: {concurrency} workers")
    print(f"    - Threshold:   Salience >= {salience_threshold} (Anomalies, peaks & advice always escalated)")
    print("-" * 80)

    start_time = time.time()
    completed_count = 0
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                evaluate_single_thread,
                t,
                api_key,
                model,
                salience_threshold
            ): t for t in thread_items
        }

        for future in as_completed(futures):
            t_data = futures[future]
            try:
                result = future.result()
                completed_count += 1

                cur.execute("""
                INSERT OR REPLACE INTO thread_triage
                (thread_id, chat_id, salience_score, escalate, primary_category, confidence, reason,
                 is_atypical, interlocutor_surprised, emotional_peak, is_advice_seeking, mentions_third_party,
                 is_relational_conflict, is_medical_or_grief_crisis, is_bizarre_or_boundary_violation,
                 is_acute_vulnerability_or_breakdown,
                 anomaly_notes, raw_response, triaged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result["thread_id"],
                    result["chat_id"],
                    result["salience_score"],
                    result["escalate"],
                    result["primary_category"],
                    result["confidence"],
                    result["reason"],
                    result.get("is_atypical", 0),
                    result.get("interlocutor_surprised", 0),
                    result.get("emotional_peak", "none"),
                    result.get("is_advice_seeking", 0),
                    result.get("mentions_third_party", 0),
                    result.get("is_relational_conflict", 0),
                    result.get("is_medical_or_grief_crisis", 0),
                    result.get("is_bizarre_or_boundary_violation", 0),
                    result.get("is_acute_vulnerability_or_breakdown", 0),
                    result.get("anomaly_notes", ""),
                    result.get("raw_response", ""),
                    now_iso
                ))
                conn.commit()

                icons = []
                if result.get("is_atypical") or result.get("interlocutor_surprised"):
                    icons.append("⚡")
                if result.get("emotional_peak") == "profound_sadness":
                    icons.append("😢")
                elif result.get("emotional_peak") == "euphoric_joy":
                    icons.append("🎉")
                elif result.get("emotional_peak") == "intense_rage":
                    icons.append("😡")
                if result.get("is_advice_seeking"):
                    icons.append("💡")
                if result.get("mentions_third_party"):
                    icons.append("👤")
                if not icons:
                    icons.append("🟢" if result["escalate"] == 1 else "⚪")

                status_icon = "".join(icons)
                badge = ""
                if result.get("is_atypical"):
                    badge += "[ATYPICAL] "
                if result.get("interlocutor_surprised"):
                    badge += "[SURPRISE] "
                if result.get("emotional_peak") != "none":
                    badge += f"[{result['emotional_peak'].upper()}] "
                if result.get("is_advice_seeking"):
                    badge += "[ADVICE] "

                print(
                    f"[{completed_count:4d}/{total_to_process}] {status_icon:<4} "
                    f"Thread {result['thread_id'][:16]} | "
                    f"Score: {result['salience_score']:.1f} | "
                    f"Cat: {result['primary_category'][:16]:<16} | "
                    f"{badge}{result['reason'][:30]}"
                )

            except Exception as e:
                print(f"[!] Error triaging thread {t_data['thread_id']}: {e}", file=sys.stderr)

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"[SUCCESS] Triage completed in {elapsed:.1f}s ({total_to_process / elapsed:.1f} threads/sec).")

    print_reduction_report(conn)
    conn.close()
    return 0


def run_enrichment(
    db_path: str,
    limit: Optional[int] = None,
    force: bool = False,
    concurrency_override: Optional[int] = None,
    chat_id: Optional[str] = None,
    do_summary: bool = True,
    do_extraction: bool = True
) -> int:
    """Run Scaledown batch summaries and entity extractions on salient threads."""
    config = load_config()
    api_key = str(config.get("api_key", "")).strip()
    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
        print("[ERROR] OpenRouter API key missing in config/embeddings_config.json")
        return 2

    summary_model = str(config.get("summary_model", "scaledown/summarize")).strip()
    extraction_model = str(config.get("extraction_model", "scaledown/extract")).strip()
    concurrency = concurrency_override or int(config.get("concurrency", 4))

    conn = sqlite3.connect(db_path)
    init_triage_table(conn)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(thread_triage)")
    tcols = {col[1] for col in cur.fetchall()}

    anom_parts = ["tr.salience_score >= 2.0", "tr.is_atypical = 1", "tr.interlocutor_surprised = 1"]
    if "emotional_peak" in tcols:
        anom_parts.append("(tr.emotional_peak IS NOT NULL AND tr.emotional_peak != 'none')")
    if "is_advice_seeking" in tcols:
        anom_parts.append("tr.is_advice_seeking = 1")
    if "is_relational_conflict" in tcols:
        anom_parts.append("tr.is_relational_conflict = 1")
    if "is_medical_or_grief_crisis" in tcols:
        anom_parts.append("tr.is_medical_or_grief_crisis = 1")
    if "is_bizarre_or_boundary_violation" in tcols:
        anom_parts.append("tr.is_bizarre_or_boundary_violation = 1")
    if "is_acute_vulnerability_or_breakdown" in tcols:
        anom_parts.append("tr.is_acute_vulnerability_or_breakdown = 1")

    anomaly_expr = " OR ".join(anom_parts)
    has_tp = "mentions_third_party" in tcols
    tp_expr = "tr.mentions_third_party = 1" if has_tp else "0"

    sql = f"""
    SELECT t.thread_id, t.chat_id, t.start_date, t.message_count, t.dialogue_text,
           tr.salience_score, tr.summary_short, tr.candidate_entities,
           CASE WHEN {tp_expr} THEN 1 ELSE 0 END as is_third_party,
           CASE WHEN ({anomaly_expr}) THEN 1 ELSE 0 END as is_anomaly
    FROM threads t
    JOIN thread_triage tr ON t.thread_id = tr.thread_id
    WHERE ({tp_expr} OR {anomaly_expr})
    """
    where_extra = []
    params = []
    if chat_id:
        where_extra.append("t.chat_id = ?")
        params.append(chat_id)

    if not force:
        unprocessed_clauses = []
        if do_extraction and has_tp:
            unprocessed_clauses.append(f"({tp_expr} AND tr.candidate_entities IS NULL)")
        if do_summary:
            unprocessed_clauses.append("(tr.summary_short IS NULL)")
        if unprocessed_clauses:
            where_extra.append(f"({' OR '.join(unprocessed_clauses)})")

    if where_extra:
        sql += " AND " + " AND ".join(where_extra)

    sql += " ORDER BY tr.salience_score DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("[✓] All qualifying threads are already enriched with summaries/entities! (Use --force to regenerate).")
        conn.close()
        return 0

    tp_count = sum(1 for r in rows if r[8] == 1)
    anom_count = sum(1 for r in rows if r[9] == 1)
    print(f"[*] Starting Scaledown Batch Enrichment on {len(rows)} qualifying threads:")
    print(f"    - Third-Party Threads (Extraction + Summary): {tp_count}")
    print(f"    - Salient Anomaly Threads (Summary):           {anom_count}")
    if do_summary:
        print(f"    - Summary Model:    {summary_model}")
    if do_extraction:
        print(f"    - Extraction Model: {extraction_model}")
    print(f"    - Concurrency:      {concurrency} workers")
    print("-" * 80)

    def process_item(item):
        tid, cid, sdate, mcount, dtext, score, curr_sum, curr_ent, is_tp, is_anom = item
        new_sum = curr_sum
        new_ent = curr_ent
        needs_sum = do_summary and (is_tp or is_anom) and (force or not curr_sum)
        needs_ent = do_extraction and is_tp and (force or not curr_ent)

        if needs_sum:
            try:
                new_sum = call_openrouter_summary(dtext, summary_model, api_key)
            except Exception as e:
                new_sum = f"[Summary failed: {e}]"
        if needs_ent:
            try:
                new_ent = call_openrouter_extraction(dtext, extraction_model, api_key)
            except Exception as e:
                new_ent = json.dumps([{"error": str(e)}])
        return tid, new_sum, new_ent

    completed = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(process_item, r): r[0] for r in rows}
        for fut in as_completed(future_map):
            tid, s_val, e_val = fut.result()
            cur.execute("""
            UPDATE thread_triage
            SET summary_short = COALESCE(?, summary_short),
                candidate_entities = COALESCE(?, candidate_entities)
            WHERE thread_id = ?;
            """, (s_val, e_val, tid))
            conn.commit()
            completed += 1
            print(f"[{completed}/{len(rows)}] Enriched thread {tid}")

    conn.close()
    print(f"[✓] Successfully enriched {completed} threads with summaries and entity candidates.")
    return 0
