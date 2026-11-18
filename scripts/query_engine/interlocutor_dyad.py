"""System-1 Interlocutor Grounding & Dyadic Episode Mapper.

Provides automated, deterministic biographical grounding of the primary chat interlocutor
(6 vectors: occupation/chronology, location, education, relationship, family, worldview)
and algorithmic extraction & System-1 classification of pivotal dyadic interaction episodes.
"""

import json
import re
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from common.config import load_config, get_api_key


BIOGRAPHICAL_KEYWORDS = {
    "job": [
        "work", "job", "boss", "company", "office", "project", "client", "salary",
        "career", "hire", "fired", "praca", "szef", "firma", "biuro", "projekt",
        "klient", "zarobki", "korpo", "pracuję", "pracowalem", "pracowałem"
    ],
    "education": [
        "study", "studies", "university", "college", "bachelor", "master", "degree",
        "exam", "campus", "studia", "uniwersytet", "licencjat", "magisterka", "egzamin",
        "studiuję", "studiowalem", "obrona", "uczelnia"
    ],
    "location": [
        "live in", "moved to", "apartment", "city", "country", "relocate", "hometown",
        "mieszkam", "przeprowadzka", "miasto", "kraj", "mieszkanie", "pochodzę"
    ],
    "relationship": [
        "girlfriend", "wife", "dating", "broke up", "single", "partner", "married",
        "dziewczyna", "żona", "randka", "rozstanie", "singiel", "partnerka"
    ],
    "family": [
        "my father", "my mother", "mom", "dad", "brother", "sister", "parents",
        "mama", "tata", "brat", "siostra", "rodzice", "rodzina", "ojciec", "matka"
    ],
    "worldview": [
        "atheist", "agnostic", "religion", "church", "god", "faith", "islam", "christian",
        "ateista", "agnostyk", "religia", "kościół", "bóg", "wiara", "katolik"
    ]
}


def get_primary_interlocutor(conn: sqlite3.Connection, chat_id: str) -> Optional[str]:
    """Identify the primary conversational partner (sender with most messages other than subject)."""
    cur = conn.cursor()
    cur.execute("SELECT chat_name FROM chats WHERE chat_id = ? LIMIT 1;", (chat_id,))
    row = cur.fetchone()
    subject = (row[0] or "").strip().lower() if row else ""

    cur.execute("""
    SELECT sender, count(*) as cnt FROM messages
    WHERE chat_id = ? AND sender IS NOT NULL AND trim(sender) != ''
    GROUP BY sender
    ORDER BY cnt DESC;
    """, (chat_id,))
    rows = cur.fetchall()
    for s, cnt in rows:
        clean_s = s.strip()
        if clean_s.lower() != subject and not subject.startswith(clean_s.lower()):
            return clean_s
    return rows[1][0].strip() if len(rows) > 1 else (rows[0][0].strip() if rows else None)


def _call_decisions_api(payload: Dict[str, Any], api_key: str, max_retries: int = 3) -> Dict[str, Any]:
    """Execute POST request to OpenRouter Decisions API with retry backoff."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Interlocutor Dyad Engine"
    }
    req_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API HTTP {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.2 ** attempt)
                continue
            raise e
    return {}


def extract_autobiographical_candidates(
    conn: sqlite3.Connection,
    chat_id: str,
    interlocutor: str,
    limit_per_domain: int = 6
) -> Dict[str, List[Dict[str, Any]]]:
    """Filter messages where sender == interlocutor for autobiographical keyword hits."""
    cur = conn.cursor()
    domain_candidates: Dict[str, List[Dict[str, Any]]] = {d: [] for d in BIOGRAPHICAL_KEYWORDS}

    for domain, kws in BIOGRAPHICAL_KEYWORDS.items():
        like_clauses = " OR ".join(["lower(text) LIKE ?" for _ in kws])
        params = [chat_id, interlocutor] + [f"%{kw}%" for kw in kws]
        sql = f"""
        SELECT id, thread_id, date, text
        FROM messages
        WHERE chat_id = ? AND sender = ? AND text IS NOT NULL AND length(text) >= 10
          AND ({like_clauses})
        ORDER BY date ASC;
        """
        cur.execute(sql, params)
        rows = cur.fetchall()
        
        # Pick distributed samples if many rows exist
        if len(rows) > limit_per_domain:
            step = len(rows) / limit_per_domain
            picked = [rows[int(i * step)] for i in range(limit_per_domain)]
        else:
            picked = rows

        for r in picked:
            domain_candidates[domain].append({
                "message_id": r[0],
                "thread_id": r[1],
                "timestamp": r[2],
                "text": r[3]
            })
    return domain_candidates


def evaluate_grounding_candidate_system1(
    candidate: Dict[str, Any],
    domain: str,
    api_key: str,
    model: str
) -> Optional[Dict[str, Any]]:
    """Evaluate candidate utterance via System-1 to extract grounded fact and verbatim quote."""
    text_snippet = candidate["text"][:1200]
    payload = {
        "model": model,
        "state": f"SPEAKER AUTOBIOGRAPHICAL UTTERANCE [{candidate['timestamp']}]:\n{text_snippet}",
        "questions": {
            "is_factual_self_disclosure": {
                "type": "noul",
                "instructions": (
                    f"Does the speaker disclose an authentic, factual personal detail about their own {domain} "
                    f"(NOT hypothetical, NOT a joke, NOT referring to someone else)?"
                )
            },
            "status_nature": {
                "type": "choice",
                "instructions": f"What is the factual status regarding {domain} disclosed here?",
                "criteria": {
                    "active_current": "An active, confirmed current reality or completed milestone",
                    "historical_past": "A past status, previous job, or former reality",
                    "unexecuted_plan": "A future desire, proposal, wish, or unconfirmed plan",
                    "not_applicable": "Not an authentic personal self-disclosure"
                }
            },
            "verbatim_fact": {
                "type": "locate",
                "instructions": f"Locate the exact verbatim clause or sentence confirming the personal fact regarding {domain}."
            }
        }
    }
    res = _call_decisions_api(payload, api_key)
    decisions = res.get("decisions", {})
    p_fact = decisions.get("is_factual_self_disclosure", {}).get("probability", 0.0)
    status = decisions.get("status_nature", {}).get("choice", "not_applicable")
    quote_obj = decisions.get("verbatim_fact", {})
    quote_text = quote_obj.get("text", "").strip() if quote_obj else ""

    if p_fact >= 0.65 and status in ("active_current", "historical_past") and quote_text:
        return {
            "domain": domain,
            "message_id": candidate["message_id"],
            "thread_id": candidate["thread_id"],
            "timestamp": candidate["timestamp"],
            "status": status,
            "confidence": round(p_fact, 3),
            "verbatim_quote": quote_text
        }
    return None


def reconcile_chronology_system1(
    facts: List[Dict[str, Any]],
    domain: str,
    api_key: str,
    model: str
) -> Dict[str, Any]:
    """Reconcile multiple chronological facts in the same domain (e.g. past job vs corporate job)."""
    if not facts:
        return {"domain": domain, "summary": "No verified data", "current": None, "history": []}
    if len(facts) == 1:
        f = facts[0]
        return {
            "domain": domain,
            "summary": f["verbatim_quote"],
            "current": f,
            "history": []
        }

    # Sort ascending by timestamp
    sorted_facts = sorted(facts, key=lambda x: str(x.get("timestamp", "")))
    fact_a = sorted_facts[0]
    fact_b = sorted_facts[-1]

    payload = {
        "model": model,
        "state": (
            f"DOMAIN: {domain.upper()}\n"
            f"EARLIER FACT A [{fact_a['timestamp']} | #{fact_a['message_id']}]: \"{fact_a['verbatim_quote']}\"\n"
            f"LATER FACT B [{fact_b['timestamp']} | #{fact_b['message_id']}]: \"{fact_b['verbatim_quote']}\""
        ),
        "questions": {
            "chronological_relation": {
                "type": "choice",
                "instructions": "Determine the chronological relationship between earlier FACT A and later FACT B:",
                "criteria": {
                    "career_or_status_progression": "FACT B is a later career/milestone evolution superseding FACT A over time",
                    "parallel_or_combined": "Both facts are true simultaneously (e.g. dual roles, side-gig)",
                    "contradiction_or_joke": "One of the facts is inaccurate, sarcastic, or retracted",
                    "unrelated": "The statements refer to unrelated topics"
                }
            },
            "current_effective_status": {
                "type": "choice",
                "instructions": "Which statement represents the current / latest established reality?",
                "criteria": {
                    "fact_b_latest": "FACT B is the latest active reality",
                    "both_valid": "Both are concurrently valid",
                    "fact_a_only": "FACT A remains valid",
                    "unresolved": "Ambiguous"
                }
            }
        }
    }
    res = _call_decisions_api(payload, api_key)
    decisions = res.get("decisions", {})
    rel = decisions.get("chronological_relation", {}).get("choice", "career_or_status_progression")

    if rel == "career_or_status_progression":
        summary = f"{fact_b['verbatim_quote']} (Since {fact_b['timestamp'][:7]}; Previously: {fact_a['verbatim_quote']} [{fact_a['timestamp'][:7]}])"
    else:
        summary = f"{fact_b['verbatim_quote']} [{fact_b['timestamp'][:10]}]"

    return {
        "domain": domain,
        "summary": summary,
        "current": fact_b,
        "history": sorted_facts[:-1],
        "relation_type": rel
    }


def extract_dyad_episodes(conn: sqlite3.Connection, chat_id: str, interlocutor: str) -> List[Dict[str, Any]]:
    """Algorithmic selection of 10-12 key dyad interaction episodes across chat lifetime."""
    cur = conn.cursor()
    cur.execute("SELECT chat_name FROM chats WHERE chat_id = ? LIMIT 1;", (chat_id,))
    row = cur.fetchone()
    subject = (row[0] or "").strip()

    episodes: List[Dict[str, Any]] = []
    seen_threads: Set[str] = set()

    # 1. Genesis (first 2 threads in chronological history)
    cur.execute("SELECT thread_id, start_date, message_count FROM threads WHERE chat_id = ? ORDER BY start_date ASC LIMIT 2;", (chat_id,))
    for tid, st, cnt in cur.fetchall():
        if tid not in seen_threads:
            seen_threads.add(tid)
            episodes.append({"thread_id": tid, "category": "genesis", "reason": "Relationship start / initial contact", "start_date": st})

    # 2. Emotional Peaks & Intensive engagement (threads with high subject word count)
    cur.execute("""
    SELECT t.thread_id, t.start_date, count(m.id) as msg_cnt, avg(m.char_count) as avg_len
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id AND m.chat_id = t.chat_id
    WHERE t.chat_id = ? AND m.sender LIKE ? AND length(m.text) >= 15
    GROUP BY t.thread_id
    HAVING msg_cnt >= 8 AND avg_len >= 120
    ORDER BY avg_len DESC
    LIMIT 4;
    """, (chat_id, f"%{subject}%"))
    for tid, st, cnt, avg_len in cur.fetchall():
        if tid not in seen_threads:
            seen_threads.add(tid)
            episodes.append({"thread_id": tid, "category": "deep_vulnerability", "reason": f"High emotional disclosure (avg words: {int(avg_len/5)})", "start_date": st})

    # 3. Long conversations (multi-turn back-and-forth)
    cur.execute("""
    SELECT thread_id, start_date, message_count FROM threads
    WHERE chat_id = ?
    ORDER BY message_count DESC
    LIMIT 4;
    """, (chat_id,))
    for tid, st, cnt in cur.fetchall():
        if tid not in seen_threads and len(episodes) < 10:
            seen_threads.add(tid)
            episodes.append({"thread_id": tid, "category": "extended_dialogue", "reason": f"Extended discussion ({cnt} messages)", "start_date": st})

    # 4. Threads surrounding long silences (>24h gaps)
    cur.execute("""
    SELECT after_thread_id, silence_duration_hours FROM silence_gaps
    WHERE chat_id = ? AND silence_duration_hours >= 48
    ORDER BY silence_duration_hours DESC LIMIT 2;
    """, (chat_id,))
    for tid, gh in cur.fetchall():
        if tid and tid not in seen_threads and len(episodes) < 12:
            seen_threads.add(tid)
            episodes.append({"thread_id": tid, "category": "silence_reconnection", "reason": f"Reconnection after {int(gh)}h silence", "start_date": ""})

    return sorted(episodes, key=lambda x: str(x.get("start_date", "")))


def classify_dyad_episode_system1(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    api_key: str,
    model: str
) -> Optional[Dict[str, Any]]:
    """Evaluate dyadic exchange using System-1 Decisions API to classify dynamic and extract quote."""
    cur = conn.cursor()
    cur.execute("""
    SELECT id, date, sender, text FROM messages
    WHERE chat_id = ? AND thread_id = ?
    ORDER BY date ASC LIMIT 40;
    """, (chat_id, thread_id))
    rows = cur.fetchall()
    if not rows or len(rows) < 4:
        return None

    transcript_lines = [f"[#{r[0]} | {r[1]} | {r[2]}]: {r[3][:300]}" for r in rows]
    state_text = "\n".join(transcript_lines)[:24000]

    payload = {
        "model": model,
        "state": f"CONVERSATION TRANSCRIPT (Thread {thread_id}):\n{state_text}",
        "questions": {
            "interaction_type": {
                "type": "choice",
                "instructions": "Classify the predominant relational and psychological dynamic in this exchange:",
                "criteria": {
                    "mentor_reality_filter": "Interlocutor provides rational advice, reality check, or calms subject's distress",
                    "vulnerability_confession": "Subject discloses deep fear, personal struggle, family pressure, or emotional pain",
                    "worldview_friction": "Friction, debate, or divergence on religion, ethics, lifestyle, or core values",
                    "boundary_testing": "Probing relational boundaries, intimacy, relationship status, or dating criteria",
                    "routine_collaborative": "Cooperative daily exchange, logistics, humor, or intellectual banter"
                }
            },
            "dyadic_tension": {
                "type": "score",
                "instructions": "Rate emotional intimacy depth and relational tension in this exchange (1: minimal/routine, 3: moderate personal disclosure, 5: critical turning point or intense emotional clash)."
            },
            "relational_anchor_quote": {
                "type": "locate",
                "instructions": "Locate the exact verbatim turn defining the core dyadic stance or pivotal emotional moment in this thread."
            }
        }
    }
    res = _call_decisions_api(payload, api_key)
    decisions = res.get("decisions", {})
    itype = decisions.get("interaction_type", {}).get("choice", "routine_collaborative")
    score_val = decisions.get("dyadic_tension", {}).get("score", 2)
    quote_obj = decisions.get("relational_anchor_quote", {})
    quote_text = quote_obj.get("text", "").strip() if quote_obj else ""

    return {
        "thread_id": thread_id,
        "interaction_type": itype,
        "dyadic_tension": score_val,
        "relational_anchor_quote": quote_text
    }


def build_interlocutor_grounding_card(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Execute complete automated System-1 biographical grounding pipeline for the primary interlocutor."""
    interlocutor = get_primary_interlocutor(conn, chat_id)
    if not interlocutor:
        return {"error": "No interlocutor found for chat."}

    cfg = load_config()
    api_key = get_api_key(cfg)
    model = (
        cfg.get("triage_model")
        or cfg.get("models", {}).get("system1_decider")
        or "~perplexity/pplx-decider-latest"
    )

    domain_cands = extract_autobiographical_candidates(conn, chat_id, interlocutor)
    grounded_vectors: Dict[str, Any] = {}

    for domain, cands in domain_cands.items():
        verified_facts = []
        for c in cands:
            fact = evaluate_grounding_candidate_system1(c, domain, api_key, model)
            if fact:
                verified_facts.append(fact)
        grounded_vectors[domain] = reconcile_chronology_system1(verified_facts, domain, api_key, model)

    return {
        "chat_id": chat_id,
        "interlocutor": interlocutor,
        "vectors": grounded_vectors,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


def build_dyad_episodes_map(conn: sqlite3.Connection, chat_id: str) -> List[Dict[str, Any]]:
    """Execute complete automated System-1 dyadic episode mapping pipeline."""
    interlocutor = get_primary_interlocutor(conn, chat_id)
    if not interlocutor:
        return []

    cfg = load_config()
    api_key = get_api_key(cfg)
    model = (
        cfg.get("triage_model")
        or cfg.get("models", {}).get("system1_decider")
        or "~perplexity/pplx-decider-latest"
    )

    raw_episodes = extract_dyad_episodes(conn, chat_id, interlocutor)
    classified = []

    for ep in raw_episodes:
        c_res = classify_dyad_episode_system1(conn, chat_id, ep["thread_id"], api_key, model)
        if c_res:
            ep.update(c_res)
            classified.append(ep)

    return sorted(classified, key=lambda x: x.get("dyadic_tension", 0), reverse=True)


def print_interlocutor_grounding_report(card: Dict[str, Any]) -> None:
    """Print readable terminal report of interlocutor grounding."""
    if "error" in card:
        print(f"[!] {card['error']}")
        return

    print("\n" + "=" * 80)
    print(f"👤 INTERLOCUTOR GROUNDING CARD: {card['interlocutor'].upper()} [Chat: {card['chat_id']}]")
    print("=" * 80)
    print(f"{'Domain Vector':<20} | {'Current Grounded Status':<55}")
    print("-" * 80)

    for domain, data in card.get("vectors", {}).items():
        summary = data.get("summary", "No verified data")
        if len(summary) > 55:
            summary = summary[:52] + "..."
        print(f"{domain.capitalize():<20} | {summary:<55}")

    print("=" * 80)
    print("💡 Invariant: Use these grounded facts to anchor reality; do NOT psychoanalyze the interlocutor.\n")


def print_dyad_episodes_report(episodes: List[Dict[str, Any]], chat_id: str) -> None:
    """Print readable terminal report of key dyad interaction episodes."""
    print("\n" + "=" * 85)
    print(f"🔄 CENTRAL RELATIONAL DYAD EPISODES MATRIX [Chat: {chat_id}]")
    print("=" * 85)
    print(f"{'Thread ID':<25} | {'Type':<24} | {'Tension':<7} | {'Anchor Quote Preview'}")
    print("-" * 85)

    for ep in episodes:
        tid = ep.get("thread_id", "")
        itype = ep.get("interaction_type", "routine")
        tension = f"{ep.get('dyadic_tension', 1)}/5"
        q = (ep.get("relational_anchor_quote") or "").strip().replace("\n", " ")
        if len(q) > 25:
            q = q[:22] + "..."
        print(f"{tid:<25} | {itype:<24} | {tension:<7} | {q}")

    print("=" * 85 + "\n")
