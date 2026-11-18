"""System-1 Fact Corroboration & Dynamic Choice Deduplication Decider.

Evaluates newly discovered facts against existing domain facts in SQLite using
OpenRouter Decisions API with dynamic categorical choices. Decides whether to:
1. Merge new evidence quotes into an existing fact (corroboration).
2. Insert an entirely new distinct fact into the knowledge base.
"""

import json
import time
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from common.config import load_config, get_api_key


def _is_decision_model(model_name: str) -> bool:
    """Check if model supports native OpenRouter Decisions API."""
    m = model_name.lower()
    return "decider" in m or "systemone" in m or "jev" in m


def _call_decisions_api(
    state: str,
    questions: Dict[str, Any],
    api_key: str,
    model: str,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Execute decision schema query via OpenRouter Decisions API."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Fact Corroboration Decider"
    }
    payload = {
        "model": model,
        "state": state,
        "questions": questions
    }
    req_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("answers", {})
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API HTTP {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e
    return {}


def match_or_deduplicate_fact(
    conn: sqlite3.Connection,
    chat_id: str,
    candidate_summary: str,
    category: str,
    sphere_id: Optional[str] = None,
    candidate_quotes: Optional[List[Dict[str, Any]]] = None,
    subject: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[str, Optional[int], str]:
    """
    Evaluate candidate fact against existing facts in the same category or sphere.
    
    Returns:
        (verdict, matched_fact_id, rationale)
        verdict: 'corroborates_existing' | 'new_fact'
    """
    cur = conn.cursor()
    sql = """
    SELECT fact_id, fact_summary, category, sphere_id, coalesce(subject, '')
    FROM discovered_facts
    WHERE chat_id = ?
    """
    params: List[Any] = [chat_id]
    if sphere_id:
        sql += " AND (upper(sphere_id) = upper(?) OR category = ?)"
        params.extend([sphere_id, category])
    else:
        sql += " AND category = ?"
        params.append(category)

    if subject and str(subject).strip():
        sql += " AND (lower(coalesce(subject, '')) = lower(?) OR subject = '' OR subject IS NULL)"
        params.append(str(subject).strip())

    sql += " ORDER BY fact_id ASC LIMIT 30;"
    cur.execute(sql, params)
    existing_facts = cur.fetchall()

    if not existing_facts:
        return "new_fact", None, "no_prior_facts_in_domain"

    # Resolve config and credentials
    config = load_config()
    resolved_key = api_key or get_api_key() or config.get("api_key")
    if not resolved_key:
        return "new_fact", None, "missing_api_key_fallback_to_new"

    resolved_model = model or config.get("decider_model") or config.get("system1_model") or config.get("model")
    if not resolved_model:
        return "new_fact", None, "missing_decider_model_fallback_to_new"

    # Format state and dynamic choice criteria
    criteria: Dict[str, str] = {
        "none_new": "Entirely new, unmapped psychological fact, milestone, or distinct behavioral pattern."
    }
    state_lines = [
        f"NEW CANDIDATE FACT PROPOSAL:",
        f"- Summary: {candidate_summary.strip()}",
        f"- Category: {category} | Sphere: {sphere_id or 'General'}",
    ]
    if candidate_quotes:
        state_lines.append("- Evidence Quotes:")
        for q in candidate_quotes[:3]:
            q_text = q.get("quote") or q.get("verbatim_quote") or ""
            q_id = q.get("msg_id") or q.get("anchor_msg_id") or ""
            state_lines.append(f"  * [#{q_id}] {q_text[:180]}")

    state_lines.append("\nEXISTING FACTS ALREADY RECORDED IN THIS DOMAIN:")
    for r in existing_facts:
        f_id, f_sum, f_cat, f_sph, f_subj = r
        opt_key = f"fact_{f_id}"
        criteria[opt_key] = f"Fact #{f_id}: {f_sum.strip()[:140]}"
        state_lines.append(f"- [{opt_key}]: {f_sum.strip()[:200]}")

    questions = {
        "matched_fact": {
            "type": "choice",
            "instructions": (
                "Evaluate whether the new candidate fact describes the EXACT same underlying psychological trait, "
                "biographical milestone, or conflict pattern as one of the existing facts (meaning it should merely "
                "corroborate it with new quotes), or if it constitutes a separate distinct fact."
            ),
            "criteria": criteria
        },
        "is_exact_corroboration": {
            "type": "noul",
            "instructions": (
                "Is the candidate proposal a direct substantive corroboration/repetition of the selected existing fact, "
                "such that attaching new quotes to that existing fact preserves epistemic accuracy without losing a distinct insight?"
            )
        }
    }

    try:
        answers = _call_decisions_api("\n".join(state_lines), questions, resolved_key, resolved_model)
    except Exception as e:
        # Non-fatal error during decider check -> default safely to new fact
        return "new_fact", None, f"decider_error_safe_insert_new: {str(e)[:80]}"

    choice_val = answers.get("matched_fact", {}).get("choice", "none_new")
    noul_prob = float(answers.get("is_exact_corroboration", {}).get("noul", 0.0))

    if choice_val != "none_new" and choice_val.startswith("fact_") and noul_prob >= 0.5:
        try:
            matched_id = int(choice_val.replace("fact_", ""))
            return "corroborates_existing", matched_id, f"System-1 matched Fact #{matched_id} (p_corroboration={noul_prob:.3f})"
        except ValueError:
            pass

    return "new_fact", None, f"System-1 classified as novel distinct fact (choice={choice_val}, p_corroboration={noul_prob:.3f})"
