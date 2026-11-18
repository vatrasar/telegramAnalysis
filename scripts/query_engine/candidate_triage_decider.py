"""System-1 candidate entity screening and triage engine via OpenRouter Decisions API.

Screens candidate mentions extracted during Stage 1 Scaledown triage, rapidly classifying them
into legitimate interpersonal third parties vs. transactional service workers, collective/abstract
terms, or self-mentions. Automatically registers discarded noise words into chat_descriptors.
"""

import json
import sqlite3
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from common.config import load_config, get_api_key
from .candidate_inspect import get_candidate_entities_data, add_noise_words


def ensure_candidate_triage_tables(conn: sqlite3.Connection) -> None:
    """Ensure candidate_triage_screened table exists."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS candidate_triage_screened (
        chat_id TEXT NOT NULL,
        mention TEXT NOT NULL,
        decision TEXT NOT NULL,
        entity_nature TEXT NOT NULL,
        relational_domain TEXT,
        confidence REAL NOT NULL,
        source_roles TEXT,
        occurrence_count INTEGER,
        screened_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, mention)
    );
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_candidate_triage_decision
    ON candidate_triage_screened(chat_id, decision);
    """)
    conn.commit()


def build_candidate_triage_questions() -> Dict[str, Any]:
    """Build questions schema for OpenRouter Decisions API candidate screening."""
    return {
        "entity_nature": {
            "type": "choice",
            "instructions": "Classify the exact nature of this candidate entity mention:",
            "criteria": {
                "legitimate_third_party": (
                    "A distinct, identifiable human individual (named contact, family member, friend, lover, "
                    "ex-partner, colleague, boss, doctor, therapist) personally interacting with or personally known to the participants. "
                    "STRICT EXCLUSION: Do NOT select this for famous public figures, celebrities, pop stars, actors, or politicians."
                ),
                "transactional_service": (
                    "A transient, one-off service or transactional worker with zero personal or relational connection "
                    "(e.g., courier, taxi driver, random cashier, tyre mechanic, waiter, delivery guy)."
                ),
                "collective_or_abstract": (
                    "A famous public figure, celebrity, politician, collective plural group, demographic category, nationality, deity, abstract concept, "
                    "or linguistic artifact (e.g., Brad Pitt, Donald Trump, kids, people, god, prophet, indonesian guys, polish people, crowd)."
                ),
                "participant_self_mention": (
                    "Direct mention of the primary chat subject or interlocutor themselves."
                )
            }
        },
        "is_interpersonal_relation": {
            "type": "noul",
            "instructions": (
                "Does this mention refer to a real-world third-party individual who had personal, "
                "meaningful interpersonal contact or personal interaction with the chat participants?"
            )
        },
        "relational_domain": {
            "type": "choice",
            "instructions": "If this is a legitimate third party, identify their primary relational domain:",
            "criteria": {
                "family": "Core family, parents, siblings, or extended kinship",
                "romantic_ex": "Romantic interest, suitor, spouse, partner, dating app match, or ex-partner",
                "work_education": "Coworker, boss, employee, client, teacher, classmate, or professional contact",
                "medical_health": "Doctor, therapist, psychiatrist, psychologist, nurse, or healthcare provider",
                "social_friend": "Friend, peer, neighbor, or social acquaintance",
                "none": "Not a legitimate third-party individual"
            }
        }
    }


def _call_decisions_api(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """Execute POST request to OpenRouter Decisions API with retry logic."""
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


def evaluate_candidate_system1(
    mention: str,
    roles: List[str],
    count: int,
    snippets: List[str],
    api_key: str,
    model: str
) -> Dict[str, Any]:
    """Evaluate a candidate mention using System-1 OpenRouter Decisions API or Chat fallback."""
    state_lines = [
        f"Candidate Mention: '{mention}'",
        f"Associated Roles: {', '.join(roles) if roles else 'unspecified'}",
        f"Thread Occurrences: {count}"
    ]
    if snippets:
        state_lines.append("Contextual Evidence from Threads:")
        for idx, snip in enumerate(snippets[:3], 1):
            state_lines.append(f"[{idx}] {snip}")

    state_text = "\n".join(state_lines)
    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        url = "https://openrouter.ai/api/alpha/decisions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
            "X-Title": "Candidate Entity Screening System-1 Decision"
        }
        payload = {
            "model": model,
            "state": state_text[:8000],
            "questions": build_candidate_triage_questions()
        }
        resp = _call_decisions_api(url, headers, payload)
        answers = resp.get("answers", {})

        nature_choice = answers.get("entity_nature", {}).get("choice", "collective_or_abstract")
        rel_noul = float(answers.get("is_interpersonal_relation", {}).get("noul", 0.0))
        domain_choice = answers.get("relational_domain", {}).get("choice", "none")

        is_legitimate = (nature_choice == "legitimate_third_party") and (rel_noul >= 0.45)
        decision = "keep" if is_legitimate else "discard"

        return {
            "mention": mention,
            "decision": decision,
            "entity_nature": nature_choice,
            "relational_domain": domain_choice if is_legitimate else "none",
            "confidence": rel_noul
        }
    else:
        chat_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
            "X-Title": "Candidate Entity Screening System-1 Fallback"
        }
        system_prompt = (
            "You are a strict candidate entity classifier for conversational forensic psychology.\n"
            "Classify whether the mention is a legitimate third party, transactional service worker, "
            "collective/abstract term, or self-mention.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "entity_nature": "legitimate_third_party"|"transactional_service"|"collective_or_abstract"|"participant_self_mention",\n'
            '  "is_interpersonal_relation": float (0.0 to 1.0),\n'
            '  "relational_domain": "family"|"romantic_ex"|"work_education"|"medical_health"|"social_friend"|"none"\n'
            "}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state_text[:8000]}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(chat_url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        raw_content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        parsed = json.loads(raw_content)
        nature = parsed.get("entity_nature", "collective_or_abstract")
        rel_prob = float(parsed.get("is_interpersonal_relation", 0.0))
        domain = parsed.get("relational_domain", "none")

        is_legitimate = (nature == "legitimate_third_party") and (rel_prob >= 0.45)
        decision = "keep" if is_legitimate else "discard"

        return {
            "mention": mention,
            "decision": decision,
            "entity_nature": nature,
            "relational_domain": domain if is_legitimate else "none",
            "confidence": rel_prob
        }


def fetch_candidate_context_snippets(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_ids: List[str],
    mention: str,
    max_threads: int = 3
) -> List[str]:
    """Retrieve summaries or targeted snippet context for a candidate mention across threads."""
    snippets: List[str] = []
    cur = conn.cursor()

    for tid in thread_ids[:max_threads]:
        cur.execute("""
        SELECT summary_short FROM thread_triage
        WHERE chat_id = ? AND thread_id = ? AND summary_short IS NOT NULL;
        """, (chat_id, tid))
        s_row = cur.fetchone()
        if s_row and s_row[0]:
            snippets.append(f"Thread {tid} Summary: {s_row[0]}")
            continue

        # Fallback to sample messages mentioning the candidate or first dialogue messages
        cur.execute("""
        SELECT sender, text FROM messages
        WHERE chat_id = ? AND thread_id = ? AND text LIKE ?
        ORDER BY message_id ASC LIMIT 3;
        """, (chat_id, tid, f"%{mention}%"))
        m_rows = cur.fetchall()
        if m_rows:
            diag = " | ".join(f"{r[0]}: {r[1]}" for r in m_rows)
            snippets.append(f"Thread {tid}: {diag}")
        else:
            cur.execute("""
            SELECT sender, text FROM messages
            WHERE chat_id = ? AND thread_id = ? AND text IS NOT NULL
            ORDER BY message_id ASC LIMIT 2;
            """, (chat_id, tid))
            early_rows = cur.fetchall()
            if early_rows:
                diag = " | ".join(f"{r[0]}: {r[1]}" for r in early_rows)
                snippets.append(f"Thread {tid} (intro): {diag}")

    return snippets


def run_candidate_triage_system1(
    db_path: str,
    chat_id: str,
    model_override: Optional[str] = None,
    auto_discard: bool = True,
    concurrency: int = 6,
    limit: Optional[int] = None,
    force: bool = False,
    json_output: bool = False
) -> Dict[str, Any]:
    """Execute high-throughput System-1 triage across candidate entities."""
    config = load_config()
    api_key = get_api_key(config)
    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
        err = "Valid OpenRouter API key required in config/embeddings_config.json for System-1 triage."
        if json_output:
            print(json.dumps({"error": err}))
        else:
            print(f"[ERROR] {err}")
        return {"error": err}

    model = model_override or config.get("triage_model") or "perplexity/pplx-decider-v1.3"

    conn = sqlite3.connect(db_path)
    ensure_candidate_triage_tables(conn)

    # 1. Fetch raw candidates
    cdata = get_candidate_entities_data(
        db_path=db_path,
        chat_id=chat_id,
        min_count=1,
        filter_noise=True,
        limit=None
    )
    raw_candidates = cdata.get("candidates", [])

    if not raw_candidates:
        conn.close()
        res = {"status": "empty", "message": "No candidates found for triage."}
        if json_output:
            print(json.dumps(res, indent=2))
        else:
            print("[*] No pending candidate entities found for chat.")
        return res

    # 2. Filter out candidates already screened in previous runs (unless force=True)
    cur = conn.cursor()
    already_screened: Set[str] = set()
    if not force:
        cur.execute("SELECT lower(mention) FROM candidate_triage_screened WHERE chat_id = ?;", (chat_id,))
        already_screened = {r[0] for r in cur.fetchall()}

    pending = [c for c in raw_candidates if c["mention"].strip().lower() not in already_screened]
    if limit is not None and limit > 0:
        pending = pending[:limit]

    if not pending:
        cur.execute("""
        SELECT count(*),
               sum(case when decision = 'keep' then 1 else 0 end),
               sum(case when decision = 'discard' then 1 else 0 end)
        FROM candidate_triage_screened WHERE chat_id = ?;
        """, (chat_id,))
        tot, kept, disc = cur.fetchone()
        conn.close()
        res = {
            "status": "already_up_to_date",
            "chat_id": chat_id,
            "total_screened": tot or 0,
            "kept": kept or 0,
            "discarded": disc or 0
        }
        if json_output:
            print(json.dumps(res, indent=2))
        else:
            print(f"\n[✓] All candidates already screened for chat {chat_id}. (Kept: {kept}, Discarded: {disc})")
            print("    Use --suggest-clusters to generate 2-3 person clusters for entity-investigator.")
        return res

    if not json_output:
        print("\n" + "=" * 80)
        print(f"🤖 SYSTEM-1 CANDIDATE ENTITY TRIAGE [Chat: {chat_id}]")
        print(f"   Model: {model}")
        print(f"   Total Unique Candidates: {len(raw_candidates)}")
        print(f"   Already Screened:        {len(already_screened)}")
        print(f"   Candidates to Screen:    {len(pending)}")
        print(f"   Auto-Discard to Noise:   {auto_discard}")
        print("=" * 80)

    # 3. Prepare candidate evaluation tasks with snippets
    prepared_items: List[Tuple[Dict[str, Any], List[str]]] = []
    for cand in pending:
        tids = [t["thread_id"] for t in cand.get("threads", []) if "thread_id" in t]
        snippets = fetch_candidate_context_snippets(conn, chat_id, tids, cand["mention"])
        prepared_items.append((cand, snippets))

    # 4. Evaluate in parallel via ThreadPoolExecutor
    def _worker(item: Tuple[Dict[str, Any], List[str]]) -> Dict[str, Any]:
        cand, snippets = item
        mention = cand["mention"]
        roles = cand.get("roles", [])
        count = cand.get("count", 1)
        try:
            return evaluate_candidate_system1(
                mention=mention,
                roles=roles,
                count=count,
                snippets=snippets,
                api_key=api_key,
                model=model
            )
        except Exception as e:
            return {
                "mention": mention,
                "decision": "keep",
                "entity_nature": "legitimate_third_party",
                "relational_domain": "social_friend",
                "confidence": 0.5,
                "error": str(e)
            }

    results: List[Dict[str, Any]] = []
    discard_noise_words: List[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        future_map = {executor.submit(_worker, item): item[0] for item in prepared_items}
        for idx, future in enumerate(as_completed(future_map), 1):
            eval_res = future.result()
            cand = future_map[future]
            mention = eval_res["mention"]
            dec = eval_res["decision"]
            nature = eval_res["entity_nature"]
            domain = eval_res.get("relational_domain", "none")
            conf = eval_res.get("confidence", 0.0)
            roles_str = ", ".join(cand.get("roles", []))
            cnt = cand.get("count", 1)

            # Persist into SQLite
            cur.execute("""
            INSERT OR REPLACE INTO candidate_triage_screened
            (chat_id, mention, decision, entity_nature, relational_domain, confidence, source_roles, occurrence_count, screened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (chat_id, mention, dec, nature, domain, conf, roles_str, cnt, now_iso))

            if dec == "discard" and auto_discard:
                discard_noise_words.append(mention)

            results.append(eval_res)

            if not json_output:
                icon = "✓ KEEP" if dec == "keep" else "✗ DISCARD"
                badge = f"[{domain}]" if dec == "keep" else f"({nature})"
                print(f"[{idx:>3}/{len(pending)}] {icon:<9} {mention:<22} {badge:<25} (p={conf:.2f})")

    conn.commit()
    conn.close()

    # 5. Persist auto-discarded noise words into chat_descriptors
    if discard_noise_words and auto_discard:
        add_noise_words(db_path, chat_id, discard_noise_words)

    kept_candidates = [r for r in results if r["decision"] == "keep"]
    discarded_candidates = [r for r in results if r["decision"] == "discard"]

    summary = {
        "status": "success",
        "chat_id": chat_id,
        "screened_count": len(results),
        "kept_count": len(kept_candidates),
        "discarded_count": len(discarded_candidates),
        "auto_discarded_noise_words": len(discard_noise_words),
        "kept": kept_candidates,
        "discarded": discarded_candidates
    }

    if json_output:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 80)
        print(f"📊 SYSTEM-1 CANDIDATE TRIAGE SUMMARY")
        print(f"   Evaluated:      {len(results)}")
        print(f"   Legitimate:     {len(kept_candidates)} (retained for cluster investigation)")
        print(f"   Discarded:      {len(discarded_candidates)} (registered into chat_descriptors)")
        print("=" * 80)
        print("👉 NEXT RECOMMENDED STEP:")
        print(f"   python3 project/scripts/query_chat.py -C {chat_id} --suggest-clusters")
        print("=" * 80 + "\n")

    return summary
