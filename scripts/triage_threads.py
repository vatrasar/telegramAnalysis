#!/usr/bin/env python3
"""
System-1 Dialogue Thread Triage Engine.
Applies fast, typed System-1 evaluation via OpenRouter to screen ALL conversation
threads in the SQLite database (chat.db).
Supports both OpenRouter Decision Models (POST /api/alpha/decisions, e.g. pplx-decider, jev)
and standard Chat Completions models (POST /api/v1/chat/completions).
Detects high-salience psychological disclosures, behavioral anomalies, and interlocutor
surprise/shock, while eliminating conversational noise before deep LLM analysis.
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import datetime
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # project/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # project
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "embeddings_config.json")
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "chat.db")


def load_config() -> Dict[str, Any]:
    """Load configuration from config/embeddings_config.json."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file missing at: {CONFIG_PATH}\n"
            f"Run 'python3 project/scripts/setup_config.py' to generate a clean template."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def init_triage_table(conn: sqlite3.Connection):
    """Ensure the thread_triage table exists in the database with anomaly detection columns."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_triage (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        salience_score REAL NOT NULL,
        escalate INTEGER NOT NULL,
        primary_category TEXT NOT NULL,
        confidence REAL NOT NULL,
        reason TEXT,
        is_atypical INTEGER DEFAULT 0,
        interlocutor_surprised INTEGER DEFAULT 0,
        anomaly_notes TEXT,
        raw_response TEXT,
        triaged_at TEXT NOT NULL
    );
    """)
    # Check for existing table schema migrations
    cur.execute("PRAGMA table_info(thread_triage)")
    existing_cols = {col[1] for col in cur.fetchall()}
    if "is_atypical" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_atypical INTEGER DEFAULT 0")
    if "interlocutor_surprised" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN interlocutor_surprised INTEGER DEFAULT 0")
    if "anomaly_notes" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN anomaly_notes TEXT")
    if "content_hash" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN content_hash TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_escalate ON thread_triage(escalate);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_score ON thread_triage(salience_score);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_atypical ON thread_triage(is_atypical);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_surprised ON thread_triage(interlocutor_surprised);")
    conn.commit()


def call_openrouter_decisions(
    dialogue_text: str,
    model: str,
    api_key: str,
    salience_threshold: float,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Call OpenRouter Decisions API (POST /api/alpha/decisions) for native System-1 decision models."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Thread Triage Decisions"
    }

    trimmed_text = dialogue_text[:20000]

    payload = {
        "model": model,
        "state": trimmed_text,
        "questions": {
            "escalate_to_llm": {
                "type": "noul",
                "instructions": (
                    "Does this conversation thread contain substantive psychological, emotional, "
                    "biographical, relational, or ideological content worth analyzing?"
                )
            },
            "salience_score": {
                "type": "score",
                "instructions": "Rate the psychological diagnostic relevance and substantive depth of this dialogue.",
                "criteria": [
                    "Pure noise: routine greetings, short scheduling, links/memes without comment, trivial small talk",
                    "Low relevance: casual chitchat with minimal personal or emotional substance",
                    "Moderate: noticeable emotional expression, interpersonal dynamic, or personal life reflection",
                    "High: significant disclosure, vulnerability, emotional conflict, or core worldview assertion",
                    "Critical: foundational trauma, formative life turning point, or major relational rupture"
                ]
            },
            "primary_category": {
                "type": "choice",
                "instructions": "What is the primary psychological category of this dialogue?",
                "criteria": {
                    "trivial_logistics": "Routine scheduling, greetings, links without comment",
                    "biographical_fact": "Biographical facts, family background, health, career milestones",
                    "emotional_vulnerability": "Vulnerability, fear, shame, grief, emotional confessions",
                    "relational_conflict_or_boundary": "Friction, arguments, emotional coldness, boundary setting",
                    "values_and_worldview": "Core beliefs, moral stances, worldview, philosophy",
                    "defense_or_coping": "Psychological defenses, rationalization, projection, avoidance"
                }
            },
            "is_atypical": {
                "type": "noul",
                "instructions": (
                    "Do the behaviors, declarations, stories, or emotional reactions deviate markedly "
                    "from normal social or conversational baselines (e.g. bizarre claims, violent outbursts, taboo disclosures)?"
                )
            },
            "interlocutor_surprised": {
                "type": "noul",
                "instructions": (
                    "Does any interlocutor exhibit shock, disbelief, cognitive dissonance, confusion, "
                    "or call out unexpected behavior ('wait what?', 'seriously?', 'since when?')?"
                )
            }
        }
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            answers = resp_data.get("answers", {})

            esc_noul = float(answers.get("escalate_to_llm", {}).get("noul", 0.0))
            score_data = answers.get("salience_score", {})
            score = float(score_data.get("score", 0.0))
            confidence = float(score_data.get("confidence", 0.8))

            cat_data = answers.get("primary_category", {})
            cat = str(cat_data.get("choice", cat_data.get("value", "trivial_logistics")))

            is_atypical = 1 if float(answers.get("is_atypical", {}).get("noul", 0.0)) >= 0.5 else 0
            interlocutor_surprised = 1 if float(answers.get("interlocutor_surprised", {}).get("noul", 0.0)) >= 0.5 else 0

            has_anomaly = (is_atypical == 1) or (interlocutor_surprised == 1)
            if has_anomaly:
                should_escalate = True
                score = max(score, 2.5)
            else:
                should_escalate = (esc_noul >= 0.5) or (score >= salience_threshold)
                if cat == "trivial_logistics" and score < 1.2:
                    should_escalate = False

            reason_parts = [f"cat={cat}", f"score={score:.2f}", f"esc={esc_noul:.2f}"]
            if is_atypical:
                reason_parts.append("atypical_behavior")
            if interlocutor_surprised:
                reason_parts.append("interlocutor_shock")

            return {
                "escalate": 1 if should_escalate else 0,
                "salience_score": round(score, 2),
                "confidence": round(confidence, 3),
                "primary_category": cat,
                "is_atypical": is_atypical,
                "interlocutor_surprised": interlocutor_surprised,
                "anomaly_notes": "Atypical/shock detected" if has_anomaly else "",
                "reason": ", ".join(reason_parts),
                "raw_response": json.dumps(resp_data)
            }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e

    raise RuntimeError("Max retries exceeded calling OpenRouter Decisions API.")


def call_openrouter_chat_completions(
    dialogue_text: str,
    model: str,
    api_key: str,
    salience_threshold: float,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Call OpenRouter Chat Completions endpoint with JSON output for standard LLMs."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Thread Triage Chat"
    }

    trimmed_text = dialogue_text[:16000]

    system_prompt = (
        "You are an ultra-fast, high-precision psychological triage classifier (System 1 classifier). "
        "Evaluate whether a chat conversation thread contains substantive psychological, biographical, "
        "emotional, relational, or ideological content worth analyzing for a deep personality profile, "
        "or whether it is trivial chitchat, memes, or logistics.\n\n"
        "Crucial Diagnostic Criteria:\n"
        "1. is_atypical: Set true if behaviors, declarations, stories, or emotional reactions deviate from "
        "standard social/conversational baselines (e.g., bizarre claims, disproportionate aggression, taboo disclosures).\n"
        "2. interlocutor_surprised: Set true if any interlocutor exhibits shock, disbelief, cognitive dissonance, "
        "confusion, or explicitly calls out unexpected behavior ('wait what?', 'seriously?', 'since when?').\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "escalate_to_llm": boolean,\n'
        '  "salience_score": number (0.0 to 4.0),\n'
        '  "confidence": number (0.0 to 1.0),\n'
        '  "primary_category": "trivial_logistics" | "biographical_fact" | "emotional_vulnerability" | "relational_conflict_or_boundary" | "values_and_worldview" | "defense_or_coping",\n'
        '  "is_atypical": boolean,\n'
        '  "interlocutor_surprised": boolean,\n'
        '  "anomaly_notes": "Short 1-sentence description if is_atypical or interlocutor_surprised is true, otherwise empty string",\n'
        '  "reason": "1-sentence concise diagnostic rationale"\n'
        "}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Evaluate this conversation thread:\n\n{trimmed_text}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 200
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            content = resp_data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:].strip()
            parsed = json.loads(content)

            score = float(parsed.get("salience_score", 0.0))
            escalate_bool = bool(parsed.get("escalate_to_llm", False))
            cat = str(parsed.get("primary_category", "trivial_logistics"))
            confidence = float(parsed.get("confidence", 0.8))
            reason = str(parsed.get("reason", ""))
            is_atypical = bool(parsed.get("is_atypical", False))
            interlocutor_surprised = bool(parsed.get("interlocutor_surprised", False))
            anomaly_notes = str(parsed.get("anomaly_notes", "")).strip()

            has_anomaly = is_atypical or interlocutor_surprised
            if has_anomaly:
                should_escalate = True
                score = max(score, 2.5)
            else:
                should_escalate = escalate_bool or (score >= salience_threshold)
                if cat == "trivial_logistics" and score < 1.2:
                    should_escalate = False

            return {
                "escalate": 1 if should_escalate else 0,
                "salience_score": round(score, 2),
                "confidence": round(confidence, 3),
                "primary_category": cat,
                "is_atypical": 1 if is_atypical else 0,
                "interlocutor_surprised": 1 if interlocutor_surprised else 0,
                "anomaly_notes": anomaly_notes,
                "reason": reason,
                "raw_response": content
            }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Chat API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e

    raise RuntimeError("Max retries exceeded calling OpenRouter API.")


def evaluate_single_thread(
    thread_data: Dict[str, Any],
    api_key: str,
    model: str,
    salience_threshold: float
) -> Dict[str, Any]:
    """Evaluate a single thread routing to either Decisions API or Chat API based on model type."""
    dialogue_text = thread_data["dialogue_text"]

    if not dialogue_text or len(dialogue_text.strip()) < 10:
        return {
            "thread_id": thread_data["thread_id"],
            "chat_id": thread_data["chat_id"],
            "salience_score": 0.0,
            "escalate": 0,
            "primary_category": "trivial_logistics",
            "confidence": 1.0,
            "is_atypical": 0,
            "interlocutor_surprised": 0,
            "anomaly_notes": "",
            "reason": "Thread empty or under 10 chars",
            "raw_response": "{}"
        }

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        res = call_openrouter_decisions(
            dialogue_text=dialogue_text,
            model=model,
            api_key=api_key,
            salience_threshold=salience_threshold
        )
    else:
        res = call_openrouter_chat_completions(
            dialogue_text=dialogue_text,
            model=model,
            api_key=api_key,
            salience_threshold=salience_threshold
        )

    res["thread_id"] = thread_data["thread_id"]
    res["chat_id"] = thread_data["chat_id"]
    res["content_hash"] = thread_data.get("content_hash")
    return res


def print_reduction_report(conn: sqlite3.Connection):
    """Generate and display comprehensive reduction and triage statistics."""
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM threads")
    total_threads = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM thread_triage")
    total_triaged = cur.fetchone()[0]

    if total_triaged == 0:
        print("[!] No threads have been triaged yet. Run without --status to start triage.")
        return

    cur.execute("SELECT count(*) FROM thread_triage WHERE escalate = 1")
    escalated_count = cur.fetchone()[0]
    rejected_count = total_triaged - escalated_count

    cur.execute("SELECT count(*) FROM thread_triage WHERE is_atypical = 1")
    atypical_count = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM thread_triage WHERE interlocutor_surprised = 1")
    surprised_count = cur.fetchone()[0]

    cur.execute("""
    SELECT sum(m.word_count)
    FROM messages m
    WHERE m.thread_id IN (SELECT thread_id FROM thread_triage)
    """)
    triaged_words = cur.fetchone()[0] or 0

    cur.execute("""
    SELECT sum(m.word_count)
    FROM messages m
    WHERE m.thread_id IN (SELECT thread_id FROM thread_triage WHERE escalate = 1)
    """)
    escalated_words = cur.fetchone()[0] or 0

    reduction_thread_pct = (rejected_count / total_triaged * 100.0) if total_triaged > 0 else 0.0
    word_reduction_pct = ((triaged_words - escalated_words) / triaged_words * 100.0) if triaged_words > 0 else 0.0

    print("\n" + "=" * 80)
    print("🎯 SYSTEM 1 TRIAGE (DECIDER / ROUTER) REDUCTION & ANOMALY REPORT")
    print("=" * 80)
    print(f"Total Threads in Database:      {total_threads:,}")
    print(f"Threads Evaluated by Triage:    {total_triaged:,} ({total_triaged / total_threads * 100.0:.1f}% coverage)")
    print("-" * 80)
    print(f"🟢 Threads Escalated to LLM:    {escalated_count:,} ({escalated_count / total_triaged * 100.0:.1f}%)")
    print(f"🔴 Threads Filtered as Noise:   {rejected_count:,} ({rejected_count / total_triaged * 100.0:.1f}%)")
    print(f"📉 Thread Volume Reduction:      {reduction_thread_pct:.1f}%")
    print(f"📉 Word / Token Reduction:       {word_reduction_pct:.1f}% ({triaged_words:,} words -> {escalated_words:,} words)")
    print("-" * 80)
    print(f"⚡ Atypical Behavior Detected:   {atypical_count:,} threads")
    print(f"😲 Interlocutor Shock/Surprise:   {surprised_count:,} threads")
    print("=" * 80)

    cur.execute("""
    SELECT primary_category, count(*), sum(case when escalate = 1 then 1 else 0 end), avg(salience_score)
    FROM thread_triage
    GROUP BY primary_category
    ORDER BY count(*) DESC
    """)
    rows = cur.fetchall()

    print("\n📊 CATEGORY BREAKDOWN:")
    print(f"{'Category':<32} {'Total':<8} {'Escalated':<12} {'Filtered':<10} {'Avg Score'}")
    print("-" * 80)
    for cat, total, esc, avg_score in rows:
        filt = total - esc
        print(f"{cat:<32} {total:<8} {esc:<12} {filt:<10} {avg_score:.2f}")

    # Showcase of detected anomalies & surprises
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           tr.is_atypical, tr.interlocutor_surprised, tr.anomaly_notes, tr.reason,
           substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.is_atypical = 1 OR tr.interlocutor_surprised = 1
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 4
    """)
    anomalies = cur.fetchall()

    if anomalies:
        print("\n⚡ DETECTED BEHAVIORAL ANOMALIES & INTERLOCUTOR SHOCKS:")
        print("-" * 80)
        for aid, adate, amsgs, ascore, acat, atyp, asurp, anotes, areason, atext in anomalies:
            flags = []
            if atyp:
                flags.append("⚡ ATYPICAL")
            if asurp:
                flags.append("😲 SURPRISED")
            flag_str = " | ".join(flags)
            print(f"[{adate}] Thread {aid} | Msgs: {amsgs} | Score: {ascore:.1f} | {flag_str}")
            if anotes:
                print(f"  Notes:   {anotes}")
            print(f"  Reason:  {areason}")
            print(f"  Snippet: {atext.strip().replace(chr(10), ' ')}...\n")

    # Showcase of captured short threads (Quiet Disclosures)
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category, tr.reason,
           substr(t.dialogue_text, 1, 100)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.escalate = 1 AND t.message_count <= 8 AND tr.is_atypical = 0 AND tr.interlocutor_surprised = 0
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 3
    """)
    short_gems = cur.fetchall()

    if short_gems:
        print("💎 CAPTURED 'QUIET DISCLOSURES' (Short threads rescued by Triage, previously lost to volume filters):")
        print("-" * 80)
        for gid, gdate, gmsgs, gscore, gcat, greason, gtext in short_gems:
            print(f"[{gdate}] Thread {gid} | Msgs: {gmsgs} | Score: {gscore:.1f} | Cat: {gcat}")
            print(f"  Reason: {greason}")
            print(f"  Snippet: {gtext.strip().replace(chr(10), ' ')}...\n")

    # Showcase of filtered noise
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           substr(t.dialogue_text, 1, 100)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.escalate = 0
    ORDER BY tr.salience_score ASC
    LIMIT 3
    """)
    noise_samples = cur.fetchall()

    if noise_samples:
        print("🗑️ FILTERED NOISE SAMPLES (Correctly pruned without burning LLM tokens):")
        print("-" * 80)
        for nid, ndate, nmsgs, nscore, ncat, ntext in noise_samples:
            print(f"[{ndate}] Thread {nid} | Msgs: {nmsgs} | Cat: {ncat} | Score: {nscore:.1f}")
            print(f"  Snippet: {ntext.strip().replace(chr(10), ' ')}...\n")
    print("=" * 80)


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

    # 1. Clean orphaned triage records (threads that no longer exist or changed ID)
    cur.execute("DELETE FROM thread_triage WHERE thread_id NOT IN (SELECT thread_id FROM threads);")
    conn.commit()

    sql = "SELECT t.thread_id, t.chat_id, t.start_date, t.duration_seconds, t.message_count, t.participants, t.initiator, t.dialogue_text, t.content_hash FROM threads t"
    where_clauses = []
    params = []

    if not force:
        where_clauses.append("""
        t.thread_id NOT IN (
            SELECT tr.thread_id 
            FROM thread_triage tr 
            WHERE tr.content_hash IS NOT NULL AND tr.content_hash = t.content_hash
        )
        """)
    if chat_id:
        where_clauses.append("t.chat_id = ?")
        params.append(chat_id)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY t.start_timestamp ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("[*] All threads in database have already been triaged with current content hashes! (Use --force to re-evaluate).")
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
            "dialogue_text": r[7],
            "content_hash": r[8]
        })

    total_to_process = len(thread_items)
    print(f"[*] Starting System-1 Triage on {total_to_process} threads:")
    print(f"    - Provider:    OpenRouter")
    print(f"    - Model:       {model}")
    print(f"    - Concurrency: {concurrency} workers")
    print(f"    - Threshold:   Salience >= {salience_threshold} (Anomalies always escalated)")
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
                 is_atypical, interlocutor_surprised, anomaly_notes, raw_response, content_hash, triaged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    result.get("anomaly_notes", ""),
                    result.get("raw_response", ""),
                    result.get("content_hash"),
                    now_iso
                ))
                conn.commit()

                if result.get("is_atypical") or result.get("interlocutor_surprised"):
                    status_icon = "⚡"
                elif result["escalate"] == 1:
                    status_icon = "🟢"
                else:
                    status_icon = "⚪"

                badge = ""
                if result.get("is_atypical"):
                    badge += "[ATYPICAL] "
                if result.get("interlocutor_surprised"):
                    badge += "[SURPRISE] "

                print(
                    f"[{completed_count:4d}/{total_to_process}] {status_icon} "
                    f"Thread {result['thread_id'][:16]} | "
                    f"Score: {result['salience_score']:.1f} | "
                    f"Cat: {result['primary_category'][:18]:<18} | "
                    f"{badge}{result['reason'][:35]}"
                )

            except Exception as e:
                print(f"[!] Error triaging thread {t_data['thread_id']}: {e}", file=sys.stderr)

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"[SUCCESS] Triage completed in {elapsed:.1f}s ({total_to_process / elapsed:.1f} threads/sec).")

    print_reduction_report(conn)
    conn.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="System-1 Dialogue Thread Triage Engine")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of threads to triage (useful for quick pilot test)")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already triaged threads")
    parser.add_argument("--concurrency", "-c", type=int, help="Number of concurrent API workers (default: 4)")
    parser.add_argument("--threshold", "-t", type=float, help="Override salience score threshold for escalation")
    parser.add_argument("--model", "-m", help="Override triage model name")
    parser.add_argument("--chat-id", help="Filter by specific chat ID")
    parser.add_argument("--status", action="store_true", help="Print existing triage and reduction report without running API")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[ERROR] Database file not found at: {args.db}")
        return 1

    if args.status:
        conn = sqlite3.connect(args.db)
        init_triage_table(conn)
        print_reduction_report(conn)
        conn.close()
        return 0

    return run_triage(
        db_path=args.db,
        limit=args.limit,
        force=args.force,
        concurrency_override=args.concurrency,
        threshold_override=args.threshold,
        model_override=args.model,
        chat_id=args.chat_id
    )


if __name__ == "__main__":
    sys.exit(main())
