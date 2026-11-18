"""System-1 automated decision module for entity thread verification and anti-conflation."""

import json
import sqlite3
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from common.config import load_config, get_api_key
except ImportError:
    from scripts.common.config import load_config, get_api_key


def get_entity_boundaries(conn: sqlite3.Connection, chat_id: str, entity_name: str) -> Dict[str, Any]:
    """Retrieve target role and audited distinct negative boundaries for an entity."""
    cur = conn.cursor()
    cur.execute("""
    SELECT verified_role, associated_descriptors FROM chat_entities
    WHERE chat_id = ? AND lower(name_or_alias) = lower(?)
    """, (chat_id, entity_name.strip()))
    row = cur.fetchone()
    role = (row[0] or "") if row else ""

    boundaries: List[Dict[str, str]] = []
    try:
        cur.execute("""
        SELECT entity_a, entity_b, reason FROM entity_disambiguation_pairs
        WHERE chat_id = ? AND (lower(entity_a) = lower(?) OR lower(entity_b) = lower(?))
        """, (chat_id, entity_name.strip(), entity_name.strip()))
        for r in cur.fetchall():
            other = r[1] if r[0].lower() == entity_name.lower().strip() else r[0]
            reason = r[2] or "Audited distinct entity"
            boundaries.append({"other_entity": other, "reason": reason})
    except Exception:
        pass

    return {
        "entity_name": entity_name.strip(),
        "role": role,
        "boundaries": boundaries
    }


def build_entity_decision_instructions(entity_info: Dict[str, Any]) -> str:
    """Build standardized, hardcoded prompt for System-1 noul proposition."""
    name = entity_info["entity_name"]
    role = entity_info.get("role", "")
    boundaries = entity_info.get("boundaries", [])

    lines = [
        f"Target Person Under Audit: '{name}'" + (f" (Role: {role})" if role else ""),
        "Objective: Determine with high calibrated confidence whether this conversation thread specifically discusses, mentions, or involves this target person."
    ]

    if boundaries:
        lines.append("CRITICAL NEGATIVE BOUNDARIES (Persons who MUST NOT be confused with target):")
        for b in boundaries:
            lines.append(f"  - NOT '{b['other_entity']}': {b['reason']}")
        lines.append(
            "Evaluation Rules:\n"
            "1. Answer TRUE (probability >= 0.5) if the target person is genuinely discussed or referenced in the thread.\n"
            "2. MULTI-ENTITY INCLUSION: If the thread discusses BOTH the target person AND one of the negative boundary persons (e.g. comparing families, discussing multiple relatives), answer TRUE.\n"
            "3. Answer FALSE (probability < 0.5) if the thread discussions solely concern a different person or only refer to one of the negative boundary individuals without involving the target person."
        )
    else:
        lines.append(
            "Evaluation Rules:\n"
            "1. Answer TRUE (probability >= 0.5) if the target person is genuinely discussed or referenced in the thread.\n"
            "2. Answer FALSE (probability < 0.5) if the discussion solely concerns incidental bystanders, celebrities, or unrelated persons."
        )

    return "\n".join(lines)


def _call_decisions_api(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """Execute low-level POST request to OpenRouter Decisions API."""
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


def verify_thread_with_system1(
    thread_state: str,
    instructions: str,
    api_key: str,
    model: str = "openrouter/decision-model"
) -> Tuple[bool, float]:
    """Verify presence of target entity in thread state via OpenRouter Decisions API."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Entity Presence System-1 Decision"
    }

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        payload = {
            "model": model,
            "state": thread_state[:12000],
            "questions": {
                "is_target_entity_present": {
                    "type": "noul",
                    "instructions": instructions
                }
            }
        }
        resp_data = _call_decisions_api(url, headers, payload)
        answers = resp_data.get("answers", {})
        prob = float(answers.get("is_target_entity_present", {}).get("noul", 0.0))
        return (prob >= 0.5, prob)
    else:
        chat_url = "https://openrouter.ai/api/v1/chat/completions"
        system_prompt = (
            "You are a native binary decision engine. Evaluate the proposition against the dialogue state.\n"
            "Respond ONLY with a valid JSON object: {\"is_target_entity_present\": boolean, \"probability\": number}"
        )
        user_prompt = f"Dialogue and Thread Context:\n{thread_state[:12000]}\n\n{instructions}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
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
        prob = float(parsed.get("probability", 0.9 if parsed.get("is_target_entity_present") else 0.1))
        return (prob >= 0.5, prob)


def filter_candidate_threads_system1(
    conn: sqlite3.Connection,
    chat_id: str,
    entity_name: str,
    candidate_thread_ids: List[str],
    max_workers: int = 6
) -> Dict[str, Dict[str, Any]]:
    """Efficiently verify candidate threads for an entity using parallel System-1 decision calls."""
    if not candidate_thread_ids:
        return {}

    try:
        config = load_config()
        api_key = get_api_key(config)
        if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
            return {}
        model = (config.get("triage_model") or "").strip()
        if not model:
            return {}
    except Exception:
        return {}

    entity_info = get_entity_boundaries(conn, chat_id, entity_name)
    instructions = build_entity_decision_instructions(entity_info)

    cur = conn.cursor()
    placeholders = ",".join("?" for _ in candidate_thread_ids)
    sql = f"""
    SELECT t.thread_id, t.start_date, t.participants, coalesce(tt.summary_short, ''), coalesce(tt.candidate_entities, '')
    FROM threads t
    LEFT JOIN thread_triage tt ON t.thread_id = tt.thread_id AND t.chat_id = tt.chat_id
    WHERE t.chat_id = ? AND t.thread_id IN ({placeholders})
    """
    cur.execute(sql, [chat_id] + list(candidate_thread_ids))
    thread_records = cur.fetchall()

    # Pre-fetch thread dialogue in the main thread to prevent SQLite cross-thread issues
    prepared_items: List[Tuple[str, str]] = []
    for rec in thread_records:
        tid, s_date, parts, summary, cand_ents = rec
        state_parts = [
            f"Thread ID: {tid} | Date: {s_date} | Participants: {parts}",
            f"Summary: {summary}" if summary else "",
            f"Extracted Candidate Mentions: {cand_ents}" if cand_ents else ""
        ]
        cur.execute("SELECT sender, text FROM messages WHERE thread_id = ? ORDER BY message_id ASC LIMIT 15", (tid,))
        m_lines = [f"{r[0]}: {r[1]}" for r in cur.fetchall() if r[1]]
        if m_lines:
            state_parts.append("Initial Dialogue Snippet:\n" + "\n".join(m_lines))
        prepared_items.append((tid, "\n".join([p for p in state_parts if p])))

    def _worker(item: Tuple[str, str]) -> Tuple[str, bool, float]:
        tid, thread_state = item
        try:
            is_present, prob = verify_thread_with_system1(thread_state, instructions, api_key, model)
            return tid, is_present, prob
        except Exception:
            # Fallback to permissive on API failure
            return tid, True, 0.5

    results: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, item): item[0] for item in prepared_items}
        for future in as_completed(futures):
            tid, is_present, prob = future.result()
            results[tid] = {
                "is_present": is_present,
                "probability": prob
            }

    return results
