"""System-1 automated decision module for anti-conflation and cohort disambiguation."""

import os
import re
import json
import time
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from common.config import load_config, get_api_key
except ImportError:
    from scripts.common.config import load_config, get_api_key

from .entities import get_chat_entities
from .conflation_audit import run_conflation_audit, resolve_entity_cluster


def _call_openrouter_json(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Execute structured JSON completion via OpenRouter API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Conflation System-1 Decider"
    }

    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    req_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                return json.loads(content)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter API HTTP {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e
    return {}


def evaluate_cohort_system1(
    cohort_title: str,
    members: List[Dict[str, Any]],
    api_key: str,
    model: str
) -> Dict[str, Any]:
    """Evaluate an entire cohort of entities with System-1 to detect duplicates or confirm distinctness."""
    lines = [f"Evaluate the following cohort of entities sharing the role/theme '{cohort_title}':\n"]
    for idx, m in enumerate(members, 1):
        name = m.get("name_or_alias") or m.get("name", "Unknown")
        role = m.get("verified_role") or m.get("role", "unspecified")
        desc = (m.get("associated_descriptors") or m.get("descriptors") or "")[:200]
        lines.append(f"{idx}. '{name}': Role: {role} | Context: {desc}")

    lines.append(
        "\nTASK:\n"
        "Determine:\n"
        "1. Are ANY two entities in this cohort suspected to be duplicate aliases of the exact same physical person?\n"
        "2. Or is the entire cohort confirmed to consist of distinct individuals?\n\n"
        "Respond strictly with JSON schema:\n"
        "{\n"
        '  "cohort_status": "all_distinct" | "duplicates_detected",\n'
        '  "duplicates_to_merge": [\n'
        '    {"source": string, "target": string, "reason": string}\n'
        "  ],\n"
        '  "distinct_reason": string (concise explanation of differentiating factors)\n'
        "}"
    )

    messages = [
        {"role": "system", "content": "You are a native System-1 entity conflation decider. Respond ONLY with valid JSON."},
        {"role": "user", "content": "\n".join(lines)}
    ]

    return _call_openrouter_json(messages, api_key, model=model)


def evaluate_pair_system1(
    e1: Dict[str, Any],
    e2: Dict[str, Any],
    api_key: str,
    model: str
) -> Dict[str, Any]:
    """Evaluate an isolated pair of entities with System-1."""
    prompt = (
        "You are a native System-1 entity conflation decider.\n"
        "Evaluate whether candidate entities could plausibly be the SAME physical human being "
        "(real conflation / duplicate alias risk), or are CLEARLY DISTINCT individuals.\n\n"
        f"Entity 1:\nName: '{e1.get('name') or e1.get('name_or_alias')}'\n"
        f"Role: {e1.get('role') or e1.get('verified_role')}\n"
        f"Context: {(e1.get('descriptors') or e1.get('associated_descriptors') or '')[:250]}\n\n"
        f"Entity 2:\nName: '{e2.get('name') or e2.get('name_or_alias')}'\n"
        f"Role: {e2.get('role') or e2.get('verified_role')}\n"
        f"Context: {(e2.get('descriptors') or e2.get('associated_descriptors') or '')[:250]}\n\n"
        "Respond strictly with JSON schema:\n"
        "{\n"
        '  "is_duplicate": boolean,\n'
        '  "verdict": "obviously_distinct" | "genuine_ambiguity",\n'
        '  "confidence": float,\n'
        '  "reason": string\n'
        "}"
    )

    messages = [
        {"role": "system", "content": "Respond ONLY with a valid JSON object matching the requested schema."},
        {"role": "user", "content": prompt}
    ]

    return _call_openrouter_json(messages, api_key, model=model)


def auto_triage_conflations(
    db_path: str,
    chat_id: str,
    model: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Automatically audit, evaluate, and resolve conflation risks via System 1."""
    config = load_config()
    api_key = get_api_key(config)
    if not api_key:
        return {"error": "OpenRouter API key missing. Configure in config/embeddings_config.json"}

    raw_model = model or config.get("triage_model")
    if not raw_model:
        return {"error": "No triage model specified via --conflation-model or configured in config/embeddings_config.json"}
    if raw_model.startswith("~"):
        raw_model = raw_model.lstrip("~")
    chosen_model = raw_model

    start_time = time.time()
    audit_res = run_conflation_audit(db_path, chat_id)
    clusters = audit_res.get("clusters", [])
    all_pairs = audit_res.get("collision_pairs", [])

    all_entities = get_chat_entities(db_path, chat_id=chat_id)
    entities_by_name = {e["name_or_alias"].lower(): e for e in all_entities}

    resolved_clusters = []
    flagged_merges = []
    resolved_pairs_count = 0

    # 1. Process clusters
    for cl in clusters:
        cid = cl["cluster_id"]
        members_names = cl["members"]
        members_objs = [entities_by_name.get(m.lower(), {"name_or_alias": m}) for m in members_names]

        res = evaluate_cohort_system1(cl["title"], members_objs, api_key, model=chosen_model)
        status = res.get("cohort_status", "all_distinct")
        distinct_reason = res.get("distinct_reason", "System-1 verified distinct cohort members.")

        if status == "all_distinct":
            if not dry_run:
                resolve_res = resolve_entity_cluster(db_path, chat_id, cid, distinct_reason)
                prs = resolve_res.get("pairs_recorded", cl.get("unresolved_pair_count", 0))
            else:
                prs = cl.get("unresolved_pair_count", 0)

            resolved_clusters.append({
                "cluster_id": cid,
                "title": cl["title"],
                "member_count": len(members_names),
                "pairs_resolved": prs,
                "reason": distinct_reason
            })
            resolved_pairs_count += prs
        else:
            merges = res.get("duplicates_to_merge", [])
            flagged_merges.extend(merges)

    # 2. Process isolated high-risk pairs
    isolated_pairs = [
        p for p in all_pairs
        if p["risk_level"] == "HIGH_RISK" and (not p.get("shared_roles") or p.get("shared_roles")[0] == "other")
    ]

    resolved_isolated = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for p in isolated_pairs:
        e1 = p["entity_1"]
        e2 = p["entity_2"]
        res = evaluate_pair_system1(e1, e2, api_key, model=chosen_model)
        verdict = res.get("verdict", "obviously_distinct")
        reason = res.get("reason", "System-1 verified distinct.")

        if verdict == "obviously_distinct" and not res.get("is_duplicate", False):
            if not dry_run:
                p1, p2 = sorted([e1["name"], e2["name"]])
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("""
                INSERT INTO entity_disambiguation_pairs (chat_id, entity_a, entity_b, status, audited_at, reason)
                VALUES (?, ?, ?, 'verified_distinct', ?, ?)
                ON CONFLICT(chat_id, entity_a, entity_b) DO UPDATE SET
                    status = 'verified_distinct', audited_at = ?, reason = ?;
                """, (chat_id, p1, p2, now_iso, reason, now_iso, reason))
                conn.commit()
                conn.close()

            resolved_isolated.append({
                "entity_1": e1["name"],
                "entity_2": e2["name"],
                "reason": reason
            })
            resolved_pairs_count += 1
        else:
            flagged_merges.append({
                "source": e1["name"],
                "target": e2["name"],
                "reason": reason
            })

    elapsed = round(time.time() - start_time, 2)

    return {
        "status": "completed",
        "chat_id": chat_id,
        "model": chosen_model,
        "elapsed_seconds": elapsed,
        "resolved_clusters_count": len(resolved_clusters),
        "resolved_clusters": resolved_clusters,
        "resolved_isolated_pairs_count": len(resolved_isolated),
        "resolved_isolated_pairs": resolved_isolated,
        "total_pairs_recorded": resolved_pairs_count,
        "flagged_merges": flagged_merges,
        "dry_run": dry_run
    }
