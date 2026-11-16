"""Inspection and extraction of candidate entities from thread triage for multi-agent clustering."""

import json
import sqlite3
from typing import Dict, Any, List, Optional, Set

NOISE_WORDS = {
    "he", "she", "him", "her", "they", "them", "his", "hers", "their", "theirs",
    "someone", "anyone", "everyone", "nobody", "no one", "somebody", "anybody", "everybody",
    "myself", "yourself", "himself", "herself", "themselves",
    "god", "prophet", "prophet muhammad", "allah", "jesus", "mahomet",
    "people", "men", "women", "man", "woman", "guy", "girl", "guys", "girls",
    "person", "persons", "child", "children", "kid", "kids",
    "random child", "random children", "classmates", "colleagues", "friends",
    "polish men", "polish women", "indonesian guys", "indonesian women",
    "white blonde men", "white blonde women", "women in europe", "indonesian", "polish"
}


def is_noise_candidate(mention: str, participants: Set[str]) -> bool:
    """Check if candidate mention is a pronoun, stopword, or primary chat participant."""
    key = mention.lower().strip()
    if len(key) <= 1:
        return True
    if key in NOISE_WORDS:
        return True
    if key in participants:
        return True
    key_clean = key.rstrip(". ,!?;:")
    if key_clean in participants or key_clean in NOISE_WORDS:
        return True
    return False


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


def get_candidate_entities_data(
    db_path: str,
    chat_id: str,
    min_count: int = 1,
    filter_noise: bool = True,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve candidate entities and their source threads for a chat with noise filtering and limits."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';
    """)
    if cur.fetchone()[0] == 0:
        conn.close()
        return {"error": "thread_triage table does not exist. Run triage first."}

    # Identify primary chat participants to prevent self-mentions as third parties
    participants: Set[str] = set()
    if filter_noise:
        try:
            cur.execute("SELECT DISTINCT sender FROM messages WHERE chat_id = ? AND sender IS NOT NULL;", (chat_id,))
            for r in cur.fetchall():
                if r[0]:
                    participants.add(r[0].lower().strip())
            cur.execute("SELECT chat_name FROM chats WHERE chat_id = ?;", (chat_id,))
            row = cur.fetchone()
            if row and row[0]:
                participants.add(row[0].lower().strip())
        except Exception:
            pass

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
            if filter_noise and is_noise_candidate(m, participants):
                continue
            key = m.lower().strip().rstrip(". ,!?;:")
            if not key:
                continue
            if key not in by_mention:
                by_mention[key] = {
                    "mention": m.rstrip(". ,!?;:"),
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
        if v["count"] < min_count:
            continue
        serialized_mentions.append({
            "canonical_key": k,
            "mention": v["mention"],
            "count": v["count"],
            "roles": sorted(list(v["roles"])),
            "threads": v["threads"]
        })

    total_candidates = len(serialized_mentions)
    displayed_candidates = serialized_mentions[:limit] if (limit and limit > 0) else serialized_mentions

    return {
        "chat_id": chat_id,
        "total_mentions": sum(m["count"] for m in serialized_mentions),
        "unique_candidate_names": total_candidates,
        "filtered_noise": filter_noise,
        "min_count": min_count,
        "limit": limit,
        "threads_with_candidates": len(threads_list),
        "candidates": displayed_candidates,
        "threads": threads_list
    }


def print_candidate_entities_summary(data: Dict[str, Any], chat_name: Optional[str] = None) -> None:
    """Print ASCII table of candidate entities extracted by Scaledown."""
    if "error" in data:
        print(f"\n[!] Error: {data['error']}")
        return

    total_names = data.get("unique_candidate_names", 0)
    candidates = data.get("candidates", [])
    limit_val = data.get("limit")
    limit_info = ""
    if limit_val and len(candidates) < total_names:
        limit_info = f" [Top {len(candidates)} of {total_names} displayed; use --limit 0 to show all]"

    c_label = f" [Chat: {chat_name or data.get('chat_id', '')}]"
    print("\n" + "=" * 80)
    print(f"👥 EXTRACTED CANDIDATE ENTITIES (SCALEDOWN EXTRACTION SUMMARY){c_label}{limit_info}")
    print(f"   Unique Candidate Mentions: {total_names} (Filtered Noise: {data.get('filtered_noise', False)}, Min Count: {data.get('min_count', 1)})")
    print(f"   Threads with Mentions:     {data.get('threads_with_candidates', 0)}")
    print(f"   Total Mention Occurrences: {data.get('total_mentions', 0)}")
    print("=" * 80)

    if not candidates:
        print("No candidate entities found matching criteria.")
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
    print("   2. Dispatch parallel `entity-investigator` subagents dynamically scaled to these clusters.")
    print("   3. Check immediately for conflation risks (e.g. shared nationality/role) via:")
    print(f"      python3 project/scripts/query_chat.py -C {data.get('chat_id')} --conflation-audit")
    print("=" * 80 + "\n")
