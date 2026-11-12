"""Inspection and extraction of candidate entities from thread triage for multi-agent clustering."""

import json
import sqlite3
from typing import Dict, Any, List, Optional


def parse_candidate_entities(raw_json: Optional[str]) -> List[Dict[str, str]]:
    """Parse candidate entities JSON safely from thread_triage table."""
    if not raw_json or raw_json.strip() in ("", "[]", "None", "null"):
        return []
    try:
        data = json.loads(raw_json)
        if isinstance(data, list):
            results = []
            for item in data:
                if isinstance(item, dict):
                    m = str(item.get("mention", "")).strip()
                    r = str(item.get("role", "")).strip()
                    if m:
                        results.append({"mention": m, "role": r})
                elif isinstance(item, str) and item.strip():
                    results.append({"mention": item.strip(), "role": ""})
            return results
        elif isinstance(data, dict):
            people = data.get("people", [])
            if isinstance(people, list):
                results = []
                for item in people:
                    if isinstance(item, dict):
                        m = str(item.get("mention", "")).strip()
                        r = str(item.get("role", "")).strip()
                        if m:
                            results.append({"mention": m, "role": r})
                return results
    except Exception:
        pass
    return []


def get_candidate_entities_data(db_path: str, chat_id: str) -> Dict[str, Any]:
    """Retrieve all candidate entities and their source threads for a chat."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';
    """)
    if cur.fetchone()[0] == 0:
        conn.close()
        return {"error": "thread_triage table does not exist. Run triage first."}

    cur.execute("""
    SELECT tt.thread_id, t.start_date, t.message_count, tt.summary_short, tt.candidate_entities
    FROM thread_triage tt
    JOIN threads t ON tt.thread_id = t.thread_id
    WHERE tt.chat_id = ? AND tt.candidate_entities IS NOT NULL AND length(trim(tt.candidate_entities)) > 2
    ORDER BY t.start_date ASC;
    """, (chat_id,))
    rows = cur.fetchall()
    conn.close()

    by_mention: Dict[str, Dict[str, Any]] = {}
    threads_list: List[Dict[str, Any]] = []

    for tid, sdate, mcount, summary, raw_candidates in rows:
        candidates = parse_candidate_entities(raw_candidates)
        if not candidates:
            continue

        thread_entry = {
            "thread_id": tid,
            "start_date": sdate,
            "message_count": mcount,
            "summary_short": summary or "",
            "candidates": candidates
        }
        threads_list.append(thread_entry)

        for c in candidates:
            m = c["mention"]
            key = m.lower().strip()
            if key not in by_mention:
                by_mention[key] = {
                    "mention": m,
                    "count": 0,
                    "roles": set(),
                    "threads": []
                }
            by_mention[key]["count"] += 1
            if c.get("role"):
                by_mention[key]["roles"].add(c["role"])
            by_mention[key]["threads"].append({
                "thread_id": tid,
                "start_date": sdate,
                "role": c.get("role", ""),
                "summary": summary or ""
            })

    # Convert sets to sorted lists for serialization
    serialized_mentions = []
    for k, v in sorted(by_mention.items(), key=lambda x: x[1]["count"], reverse=True):
        serialized_mentions.append({
            "canonical_key": k,
            "mention": v["mention"],
            "count": v["count"],
            "roles": sorted(list(v["roles"])),
            "threads": v["threads"]
        })

    return {
        "chat_id": chat_id,
        "total_mentions": sum(m["count"] for m in serialized_mentions),
        "unique_candidate_names": len(serialized_mentions),
        "threads_with_candidates": len(threads_list),
        "candidates": serialized_mentions,
        "threads": threads_list
    }


def print_candidate_entities_summary(data: Dict[str, Any], chat_name: Optional[str] = None) -> None:
    """Print ASCII table of candidate entities extracted by Scaledown."""
    if "error" in data:
        print(f"\n[!] Error: {data['error']}")
        return

    c_label = f" [Chat: {chat_name or data.get('chat_id', '')}]"
    print("\n" + "=" * 80)
    print(f"👥 EXTRACTED CANDIDATE ENTITIES (SCALEDOWN EXTRACTION SUMMARY){c_label}")
    print(f"   Unique Candidate Mentions: {data.get('unique_candidate_names', 0)}")
    print(f"   Threads with Mentions:     {data.get('threads_with_candidates', 0)}")
    print(f"   Total Mention Occurrences: {data.get('total_mentions', 0)}")
    print("=" * 80)

    candidates = data.get("candidates", [])
    if not candidates:
        print("No candidate entities extracted yet. Run `python3 project/scripts/triage_threads.py --enrich` first.")
        print("=" * 80)
        return

    print(f"{'Candidate Mention':<25} {'Count':<7} {'Associated Roles':<25} {'Thread IDs'}")
    print("-" * 80)
    for c in candidates:
        m_name = c["mention"][:24]
        cnt = str(c["count"])
        roles_str = ", ".join(c["roles"])[:24] if c["roles"] else "-"
        tids = [t["thread_id"] for t in c["threads"]]
        tids_str = ", ".join(tids[:3]) + (f" (+{len(tids)-3} more)" if len(tids) > 3 else "")
        print(f"{m_name:<25} {cnt:<7} {roles_str:<25} {tids_str}")

    print("-" * 80)
    print("💡 SUPERVISOR ACTION:")
    print("   1. Group overlapping mentions into logical character clusters.")
    print("   2. Dispatch up to 4 parallel `entity-investigator` subagents on these clusters.")
    print("   3. Check immediately for conflation risks (e.g. shared nationality/role) via:")
    print(f"      python3 project/scripts/query_chat.py -C {data.get('chat_id')} --conflation-audit")
    print("=" * 80 + "\n")
