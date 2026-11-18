"""System-1 Third-Party Entity Pre-Mapping and Grounding Decider.

Pre-maps candidate threads for a third-party entity using clean aliases,
evaluating both:
  - Module A: Biographical Factsheet (occupation, location, age/health markers, status)
  - Module B: Relational Dynamic with Subject (relational depth 1-5, conflict axis, quote)
Partitions verified threads into structured shard packages for entity-shard-auditor subagents.
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
from .sharding import _extract_clean_aliases, find_entity_threads


def _call_decisions_api(payload: Dict[str, Any], api_key: str, max_retries: int = 3) -> Dict[str, Any]:
    """Execute POST request to OpenRouter Decisions API with retry backoff."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Entity Profile Decider"
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


def evaluate_entity_thread_system1(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    entity_name: str,
    aliases: Set[str],
    api_key: str,
    model: str
) -> Optional[Dict[str, Any]]:
    """Evaluate a candidate thread for an entity, extracting Module A (Bio) and Module B (Relational)."""
    cur = conn.cursor()
    cur.execute("""
    SELECT id, date, sender, text FROM messages
    WHERE chat_id = ? AND thread_id = ?
    ORDER BY date ASC LIMIT 40;
    """, (chat_id, thread_id))
    rows = cur.fetchall()
    if not rows:
        return None

    transcript_lines = [f"[#{r[0]} | {r[1]} | {r[2]}]: {r[3][:250]}" for r in rows]
    state_text = "\n".join(transcript_lines)[:24000]

    alias_str = ", ".join([f"'{a}'" for a in aliases if len(a) >= 2])
    state_payload = (
        f"TARGET ENTITY: '{entity_name}' (Known Aliases/Patterns: {alias_str})\n\n"
        f"CONVERSATION TRANSCRIPT (Thread {thread_id}):\n{state_text}"
    )

    payload = {
        "model": model,
        "state": state_payload,
        "questions": {
            "is_entity_present": {
                "type": "noul",
                "instructions": f"Is target entity '{entity_name}' or their relationship with the subject discussed or present in this exchange?"
            },
            "relational_depth": {
                "type": "score",
                "instructions": "Rate the psychological and interpersonal salience of this entity to the subject (1: passing mention/tangential, 3: personal interaction/disclosure, 5: pivotal turning point/trauma/major conflict)."
            }
        }
    }

    res = _call_decisions_api(payload, api_key)
    decisions = res.get("decisions", {})
    p_present = decisions.get("is_entity_present", {}).get("probability", 0.0)
    score_val = decisions.get("relational_depth", {}).get("score", 1)

    if p_present < 0.45:
        return None

    def _extract_locate_text(key: str) -> str:
        obj = decisions.get(key)
        return (obj.get("text") or "").strip() if isinstance(obj, dict) else ""

    return {
        "thread_id": thread_id,
        "confidence": round(p_present, 3),
        "relational_depth": score_val,
        "module_a_bio": {
            "occupation": _extract_locate_text("occupation_job"),
            "location": _extract_locate_text("geographic_origin"),
            "markers": _extract_locate_text("biographical_markers")
        },
        "module_b_relational": {
            "anchor_quote": _extract_locate_text("relational_anchor_quote")
        }
    }


def map_entity_profile_system1(
    conn: sqlite3.Connection,
    chat_id: str,
    entity_name: str,
    batch_size: int = 4
) -> Dict[str, Any]:
    """Execute complete automated System-1 entity thread pre-mapping and biographical extraction."""
    cfg = load_config()
    api_key = get_api_key(cfg)
    model = (
        cfg.get("triage_model")
        or cfg.get("models", {}).get("system1_decider")
        or "~perplexity/pplx-decider-latest"
    )

    aliases = _extract_clean_aliases(conn, chat_id, entity_name)
    raw_threads = find_entity_threads(conn, chat_id, entity_name)

    evaluated_threads: List[Dict[str, Any]] = []
    bio_accum = {"occupations": set(), "locations": set(), "markers": set()}

    for t_item in raw_threads:
        tid = t_item.get("thread_id") if isinstance(t_item, dict) else str(t_item)
        eval_res = evaluate_entity_thread_system1(conn, chat_id, tid, entity_name, aliases, api_key, model)
        if eval_res:
            evaluated_threads.append(eval_res)
            bio = eval_res["module_a_bio"]
            if bio["occupation"]: bio_accum["occupations"].add(bio["occupation"])
            if bio["location"]: bio_accum["locations"].add(bio["location"])
            if bio["markers"]: bio_accum["markers"].add(bio["markers"])

    # Sort threads descending by relational depth
    sorted_threads = sorted(evaluated_threads, key=lambda x: x.get("relational_depth", 0), reverse=True)

    # Shard packaging if thread volume exceeds threshold
    shards = []
    if len(sorted_threads) > batch_size:
        for i in range(0, len(sorted_threads), batch_size):
            chunk = sorted_threads[i : i + batch_size]
            shards.append({
                "shard_id": (i // batch_size) + 1,
                "thread_ids": [t["thread_id"] for t in chunk],
                "avg_depth": round(sum(t["relational_depth"] for t in chunk) / len(chunk), 2)
            })

    return {
        "chat_id": chat_id,
        "entity_name": entity_name,
        "aliases": sorted(list(aliases)),
        "total_threads_found": len(sorted_threads),
        "module_a_factsheet": {
            "occupations": list(bio_accum["occupations"]),
            "locations": list(bio_accum["locations"]),
            "biographical_markers": list(bio_accum["markers"])
        },
        "threads": sorted_threads,
        "shards": shards,
        "sharding_recommended": len(sorted_threads) > 6,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


def print_entity_profile_map_report(profile_map: Dict[str, Any]) -> None:
    """Print readable terminal report of entity pre-mapping and grounding."""
    entity = profile_map["entity_name"]
    print("\n" + "=" * 85)
    print(f"🎯 SYSTEM-1 ENTITY PRE-MAPPING & GROUNDING: {entity.upper()} [Chat: {profile_map['chat_id']}]")
    print("=" * 85)
    print(f"Aliases / Search Patterns: {', '.join(profile_map['aliases'])}")
    print(f"Total Verified Threads:    {profile_map['total_threads_found']}")
    print("-" * 85)

    print("📋 MODULE A: BIOGRAPHICAL FACTSHEET (GROUNDING)")
    bio = profile_map.get("module_a_factsheet", {})
    occ = ", ".join(bio.get("occupations", [])) or "None detected"
    loc = ", ".join(bio.get("locations", [])) or "None detected"
    mar = ", ".join(bio.get("biographical_markers", [])) or "None detected"
    print(f"  • Occupation / Work: {occ}")
    print(f"  • Location / Origin: {loc}")
    print(f"  • Traits / Markers:  {mar}")
    print("-" * 85)

    print("🔍 MODULE B: VERIFIED RELATIONAL THREADS (SORTED BY DEPTH)")
    print(f"{'Thread ID':<25} | {'Depth':<7} | {'Conf':<6} | {'Relational Quote Preview'}")
    print("-" * 85)
    for t in profile_map.get("threads", []):
        tid = t["thread_id"]
        depth = f"{t.get('relational_depth', 1)}/5"
        conf = f"{t.get('confidence', 0.0):.2f}"
        q = (t.get("module_b_relational", {}).get("anchor_quote") or "").strip().replace("\n", " ")
        if len(q) > 35:
            q = q[:32] + "..."
        print(f"{tid:<25} | {depth:<7} | {conf:<6} | {q}")

    shards = profile_map.get("shards", [])
    if shards:
        print("-" * 85)
        print(f"📦 RECOMMENDED SHARD PACKAGES FOR 'entity-shard-auditor' ({len(shards)} shards):")
        for s in shards:
            tids = ", ".join(s["thread_ids"])
            print(f"  • Shard {s['shard_id']} (Avg Depth: {s['avg_depth']}): {tids}")

    print("=" * 85 + "\n")
