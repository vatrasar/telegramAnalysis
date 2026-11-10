#!/usr/bin/env python3
"""
System-1 Dialogue Thread Triage Engine.
Applies fast, typed System-1 evaluation via OpenRouter to screen ALL conversation
threads in the SQLite database (chat.db).
Supports both OpenRouter Decision Models (POST /api/alpha/decisions, e.g. pplx-decider, jev)
and standard Chat Completions models (POST /api/v1/chat/completions).

Diagnostic Radars:
1. Behavioral Anomalies & Interlocutor Shock (is_atypical, interlocutor_surprised)
2. Acute Emotional Peaks & Dyadic Gravity (emotional_peak: profound_sadness, euphoric_joy, intense_rage)
3. Confessions & Advice Seeking (is_advice_seeking)
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
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # .agents/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # .agents
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "embeddings_config.json")
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "chat.db")


def load_config() -> Dict[str, Any]:
    """Load configuration from config/embeddings_config.json."""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file missing at: {CONFIG_PATH}\n"
            f"Run 'python3 .agents/scripts/setup_config.py' to generate a clean template."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def init_triage_table(conn: sqlite3.Connection):
    """Ensure the thread_triage table exists in the database with all diagnostic radar columns."""
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
        emotional_peak TEXT DEFAULT 'none',
        is_advice_seeking INTEGER DEFAULT 0,
        mentions_third_party INTEGER DEFAULT 0,
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
    if "emotional_peak" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN emotional_peak TEXT DEFAULT 'none'")
    if "is_advice_seeking" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_advice_seeking INTEGER DEFAULT 0")
    if "mentions_third_party" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN mentions_third_party INTEGER DEFAULT 0")
    if "anomaly_notes" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN anomaly_notes TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_escalate ON thread_triage(escalate);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_score ON thread_triage(salience_score);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_atypical ON thread_triage(is_atypical);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_surprised ON thread_triage(interlocutor_surprised);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_peak ON thread_triage(emotional_peak);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_advice ON thread_triage(is_advice_seeking);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_third_party ON thread_triage(mentions_third_party);")
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
            },
            "emotional_peak": {
                "type": "choice",
                "instructions": (
                    "Does this dialogue contain an acute emotional peak or grave emotional situation "
                    "(either from direct intense feelings, tragic medical/life disclosures, or deep empathetic distress, condolences, and consoling from the interlocutor)?"
                ),
                "criteria": {
                    "none": "Routine emotional baseline, mild everyday feelings, calm conversation, or intellectual debates",
                    "profound_sadness": "Acute grief, heartbreak, despair, crying, tragic illness/family news, or deep empathetic condolences/consoling",
                    "euphoric_joy": "Intense joy, celebration, euphoric breakthrough, falling in love, relief",
                    "intense_rage": "Explosive fury, extreme indignation, verbal aggression, loss of temper"
                }
            },
            "is_advice_seeking": {
                "type": "noul",
                "instructions": (
                    "Does a participant explicitly ask for advice on a personal problem, express a moral/life dilemma ('what should I do?'), "
                    "or announce an intimate personal confession ('I need to confess something', 'can I tell you something in confidence')?"
                )
            },
            "mentions_third_party_person": {
                "type": "noul",
                "instructions": (
                    "Does this dialogue explicitly mention, discuss, quote, or introduce an external third-party person "
                    "(e.g. friend, suitor, ex-partner, coworker, boss, family member, acquaintance) other than the two main chat participants?"
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

            peak_data = answers.get("emotional_peak", {})
            emotional_peak = str(peak_data.get("choice", peak_data.get("value", "none")))
            if emotional_peak not in ("none", "profound_sadness", "euphoric_joy", "intense_rage"):
                emotional_peak = "none"

            is_advice_seeking = 1 if float(answers.get("is_advice_seeking", {}).get("noul", 0.0)) >= 0.5 else 0
            mentions_third_party = 1 if float(answers.get("mentions_third_party_person", {}).get("noul", 0.0)) >= 0.5 else 0

            # Escalation policy:
            # High priority flags ALWAYS escalate and get salience score boosted
            has_special_flag = (is_atypical == 1) or (interlocutor_surprised == 1) or (emotional_peak != "none") or (is_advice_seeking == 1)
            if has_special_flag:
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
            if emotional_peak != "none":
                reason_parts.append(f"peak:{emotional_peak}")
            if is_advice_seeking:
                reason_parts.append("advice/confession")
            if mentions_third_party:
                reason_parts.append("third_party")

            notes_parts = []
            if is_atypical:
                notes_parts.append("Atypical behavior")
            if interlocutor_surprised:
                notes_parts.append("Interlocutor surprised")
            if emotional_peak != "none":
                notes_parts.append(f"Peak: {emotional_peak}")
            if is_advice_seeking:
                notes_parts.append("Advice seeking/confession")
            if mentions_third_party:
                notes_parts.append("Mentions third party")

            return {
                "escalate": 1 if should_escalate else 0,
                "salience_score": round(score, 2),
                "confidence": round(confidence, 3),
                "primary_category": cat,
                "is_atypical": is_atypical,
                "interlocutor_surprised": interlocutor_surprised,
                "emotional_peak": emotional_peak,
                "is_advice_seeking": is_advice_seeking,
                "mentions_third_party": mentions_third_party,
                "anomaly_notes": ", ".join(notes_parts),
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
        "Crucial Diagnostic Radars:\n"
        "1. is_atypical: Set true if behaviors, declarations, stories, or emotional reactions deviate markedly "
        "from standard social/conversational baselines (e.g. bizarre claims, disproportionate aggression, taboo disclosures).\n"
        "2. interlocutor_surprised: Set true if any interlocutor exhibits shock, disbelief, cognitive dissonance, "
        "confusion, or explicitly calls out unexpected behavior ('wait what?', 'seriously?', 'since when?').\n"
        "3. emotional_peak: Set to 'profound_sadness' (acute grief, tragic news, crying, deep condolences/consoling by interlocutor), "
        "'euphoric_joy' (intense happiness, celebration, infatuation, relief), 'intense_rage' (fury, verbal aggression), or 'none'.\n"
        "4. is_advice_seeking: Set true if a participant explicitly asks for advice, expresses a personal dilemma ('what should I do?'), "
        "or announces an intimate confession ('I need to confess something').\n"
        "5. mentions_third_party: Set true if this dialogue explicitly mentions, discusses, quotes, or introduces an external third-party person "
        "(e.g. friend, suitor, ex-partner, coworker, boss, family member, acquaintance) other than the two main chat participants.\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "escalate_to_llm": boolean,\n'
        '  "salience_score": number (0.0 to 4.0),\n'
        '  "confidence": number (0.0 to 1.0),\n'
        '  "primary_category": "trivial_logistics" | "biographical_fact" | "emotional_vulnerability" | "relational_conflict_or_boundary" | "values_and_worldview" | "defense_or_coping",\n'
        '  "is_atypical": boolean,\n'
        '  "interlocutor_surprised": boolean,\n'
        '  "emotional_peak": "none" | "profound_sadness" | "euphoric_joy" | "intense_rage",\n'
        '  "is_advice_seeking": boolean,\n'
        '  "mentions_third_party": boolean,\n'
        '  "anomaly_notes": "Short 1-sentence description if special radars triggered, otherwise empty string",\n'
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
        "max_tokens": 250
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
            emotional_peak = str(parsed.get("emotional_peak", "none"))
            if emotional_peak not in ("none", "profound_sadness", "euphoric_joy", "intense_rage"):
                emotional_peak = "none"
            is_advice_seeking = bool(parsed.get("is_advice_seeking", False))
            mentions_third_party = bool(parsed.get("mentions_third_party", False))
            anomaly_notes = str(parsed.get("anomaly_notes", "")).strip()

            has_special_flag = is_atypical or interlocutor_surprised or (emotional_peak != "none") or is_advice_seeking
            if has_special_flag:
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
                "emotional_peak": emotional_peak,
                "is_advice_seeking": 1 if is_advice_seeking else 0,
                "mentions_third_party": 1 if mentions_third_party else 0,
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
            "emotional_peak": "none",
            "is_advice_seeking": 0,
            "mentions_third_party": 0,
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
    return res


def print_reduction_report(conn: sqlite3.Connection):
    """Generate and display comprehensive reduction and diagnostic radar statistics."""
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

    # Radar 1: Anomalies & Shock
    cur.execute("SELECT count(*) FROM thread_triage WHERE is_atypical = 1")
    atypical_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM thread_triage WHERE interlocutor_surprised = 1")
    surprised_count = cur.fetchone()[0]

    # Radar 2: Emotional Peaks
    cur.execute("SELECT count(*) FROM thread_triage WHERE emotional_peak != 'none'")
    peaks_count = cur.fetchone()[0]
    cur.execute("SELECT emotional_peak, count(*) FROM thread_triage WHERE emotional_peak != 'none' GROUP BY emotional_peak")
    peak_map = dict(cur.fetchall())
    sadness_count = peak_map.get("profound_sadness", 0)
    joy_count = peak_map.get("euphoric_joy", 0)
    rage_count = peak_map.get("intense_rage", 0)

    # Radar 3: Advice Seeking & Confessions
    cur.execute("SELECT count(*) FROM thread_triage WHERE is_advice_seeking = 1")
    advice_count = cur.fetchone()[0]

    # Radar 4: Third-Party Mentions
    cur.execute("SELECT count(*) FROM thread_triage WHERE mentions_third_party = 1")
    third_party_count = cur.fetchone()[0]

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
    print("🎯 SYSTEM 1 TRIAGE (DECIDER / ROUTER) REDUCTION & DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"Total Threads in Database:      {total_threads:,}")
    print(f"Threads Evaluated by Triage:    {total_triaged:,} ({total_triaged / total_threads * 100.0:.1f}% coverage)")
    print("-" * 80)
    print(f"🟢 Threads Escalated to LLM:    {escalated_count:,} ({escalated_count / total_triaged * 100.0:.1f}%)")
    print(f"🔴 Threads Filtered as Noise:   {rejected_count:,} ({rejected_count / total_triaged * 100.0:.1f}%)")
    print(f"📉 Thread Volume Reduction:      {reduction_thread_pct:.1f}%")
    print(f"📉 Word / Token Reduction:       {word_reduction_pct:.1f}% ({triaged_words:,} words -> {escalated_words:,} words)")
    print("-" * 80)
    print("🔍 DIAGNOSTIC RADARS OVERVIEW:")
    print(f"  ⚡ Radar 1 (Anomalies & Shocks):      {atypical_count + surprised_count} flags (Atypical: {atypical_count}, Surprised: {surprised_count})")
    print(f"  🎭 Radar 2 (Acute Emotional Peaks):    {peaks_count} threads (😢 Sadness/Grief: {sadness_count}, 🎉 Joy/Euphoria: {joy_count}, 😡 Rage: {rage_count})")
    print(f"  💡 Radar 3 (Confessions & Advice):     {advice_count} threads")
    print(f"  👤 Radar 4 (Third-Party Mentions):     {third_party_count} threads")
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

    # Showcase Radar 2: Acute Emotional Peaks
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.emotional_peak,
           tr.reason, substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.emotional_peak != 'none'
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 4
    """)
    peak_samples = cur.fetchall()

    if peak_samples:
        print("\n🎭 ACUTE EMOTIONAL PEAKS (Grief, Euphoria, Rage & Empathetic Consoling):")
        print("-" * 80)
        for pid, pdate, pmsgs, pscore, ptype, preason, ptext in peak_samples:
            icon = "😢" if ptype == "profound_sadness" else ("🎉" if ptype == "euphoric_joy" else "😡")
            print(f"[{pdate}] Thread {pid} | Msgs: {pmsgs} | Score: {pscore:.1f} | {icon} {ptype.upper()}")
            print(f"  Reason:  {preason}")
            teaser = ptext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {pid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

    # Showcase Radar 3: Confessions & Advice Seeking
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           tr.reason, substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.is_advice_seeking = 1
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 3
    """)
    advice_samples = cur.fetchall()

    if advice_samples:
        print("💡 INTIMATE CONFESSIONS & ADVICE SEEKING (Life Dilemmas & Decision Impasses):")
        print("-" * 80)
        for aid, adate, amsgs, ascore, acat, areason, atext in advice_samples:
            print(f"[{adate}] Thread {aid} | Msgs: {amsgs} | Score: {ascore:.1f} | Cat: {acat}")
            print(f"  Reason:  {areason}")
            teaser = atext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {aid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

    # Showcase Radar 1: Anomalies & Shock
    cur.execute("""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           tr.is_atypical, tr.interlocutor_surprised, tr.anomaly_notes, tr.reason,
           substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.is_atypical = 1 OR tr.interlocutor_surprised = 1
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 3
    """)
    anomalies = cur.fetchall()

    if anomalies:
        print("⚡ BEHAVIORAL ANOMALIES & INTERLOCUTOR SHOCKS:")
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
            teaser = atext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {aid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

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
            teaser = ntext.strip().replace(chr(10), " ")[:70]
            print(f"  Sample:  \"{teaser}...\"\n")
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
    print(f"    - Provider:    OpenRouter")
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
                 anomaly_notes, raw_response, triaged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    result.get("anomaly_notes", ""),
                    result.get("raw_response", ""),
                    now_iso
                ))
                conn.commit()

                # Generate visual status icons
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


def verify_unregistered_entities_decider(
    dialogue_text: str,
    known_names: List[str],
    model: str,
    api_key: str,
    max_retries: int = 3
) -> Tuple[bool, float]:
    """Adversarial System-1 watchdog: verify whether dialogue mentions any third-party person NOT in known_names."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Entity Watchdog Decision"
    }

    trimmed_text = dialogue_text[:16000]
    known_str = ", ".join(f"'{name}'" for name in known_names) if known_names else "none"

    instructions = (
        f"We have already identified and registered the following individuals: [{known_str}]. "
        f"Does this dialogue explicitly mention, discuss, quote, or introduce any OTHER external third-party person, suitor, "
        f"acquaintance, coworker, or relative whose personal name or identity is NOT among the registered individuals listed above?"
    )

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        payload = {
            "model": model,
            "state": trimmed_text,
            "questions": {
                "has_unregistered_third_party": {
                    "type": "noul",
                    "instructions": instructions
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
                prob = float(answers.get("has_unregistered_third_party", {}).get("noul", 0.0))
                return (prob >= 0.5, prob)
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
    else:
        chat_url = "https://openrouter.ai/api/v1/chat/completions"
        system_prompt = (
            "You are an adversarial entity verification watchdog. "
            "Determine if a conversation mentions any third-party person NOT in the provided list of known names.\n"
            "Respond ONLY with a valid JSON object: {\"has_unregistered_third_party\": boolean, \"probability\": number}"
        )
        user_prompt = f"Known registered entities: [{known_str}]\n\nDialogue text:\n{trimmed_text}\n\nQuestion: {instructions}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 100
        }
        req_data = json.dumps(payload).encode("utf-8")
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(chat_url, data=req_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                parsed = json.loads(content)
                flag = bool(parsed.get("has_unregistered_third_party", False))
                prob = float(parsed.get("probability", 1.0 if flag else 0.0))
                return (flag, prob)
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

    raise RuntimeError("Max retries exceeded calling verify_unregistered_entities_decider.")


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
