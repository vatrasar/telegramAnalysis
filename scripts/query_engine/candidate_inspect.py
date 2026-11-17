"""Inspection and extraction of candidate entities from thread triage for multi-agent clustering."""

import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

# Base multilingual stopwords and generic non-relational terms
BASE_NOISE_WORDS = {
    # English pronouns & generic terms
    "he", "she", "him", "her", "they", "them", "his", "hers", "their", "theirs",
    "someone", "anyone", "everyone", "nobody", "no one", "somebody", "anybody", "everybody",
    "myself", "yourself", "himself", "herself", "themselves",
    "god", "prophet", "prophet muhammad", "allah", "jesus", "mahomet",
    "people", "men", "women", "man", "woman", "guy", "girl", "guys", "girls",
    "person", "persons", "child", "children", "kid", "kids",
    "random child", "random children", "classmates", "colleagues", "friends",
    "polish men", "polish women", "indonesian guys", "indonesian women",
    "white blonde men", "white blonde women", "women in europe", "indonesian", "polish",
    # Polish pronouns & generic terms
    "on", "ona", "ono", "oni", "one", "go", "jego", "jej", "mu", "jejku", "ich", "im",
    "siebie", "sobie", "sobą", "ktoś", "nikt", "każdy", "wszyscy", "ktokolwiek",
    "bóg", "jezus", "allach", "allah", "prorok",
    "ludzie", "człowiek", "mężczyźni", "kobiety", "facet", "laska", "chłopak", "dziewczyna",
    "dzieci", "dziecko", "pan", "pani", "państwo"
}


def add_noise_words(db_path: str, chat_id: str, words: List[str]) -> Dict[str, Any]:
    """Register custom noise/stop words into chat_descriptors to exclude them from candidates."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now_iso = datetime.now().isoformat()
    added = []
    for w in words:
        clean_w = w.strip().lower()
        if not clean_w:
            continue
        cur.execute("""
        INSERT INTO chat_descriptors (chat_id, descriptor, cardinality, estimated_count, audited_at)
        VALUES (?, ?, 'noise', 0, ?)
        ON CONFLICT(chat_id, descriptor) DO UPDATE SET cardinality='noise', audited_at=?;
        """, (chat_id, clean_w, now_iso, now_iso))
        added.append(clean_w)
    conn.commit()
    conn.close()
    return {"chat_id": chat_id, "added_noise_words": added}


def is_noise_candidate(mention: str, participants: Set[str], custom_noise: Set[str]) -> bool:
    """Check if candidate mention is a pronoun, stopword, or primary chat participant."""
    key = mention.lower().strip()
    if len(key) <= 1:
        return True
    if key in BASE_NOISE_WORDS or key in custom_noise:
        return True
    if key in participants:
        return True
    key_clean = key.rstrip(". ,!?;:")
    if key_clean in participants or key_clean in BASE_NOISE_WORDS or key_clean in custom_noise:
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
    page: int = 1,
    page_size: Optional[int] = None,
    shard: Optional[str] = None,
    extra_noise_words: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Retrieve candidate entities and their source threads for a chat with noise filtering, sharding, and pagination."""
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
    custom_noise: Set[str] = set()

    if extra_noise_words:
        for w in extra_noise_words:
            if w.strip():
                custom_noise.add(w.strip().lower())

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

        try:
            cur.execute(
                "SELECT descriptor FROM chat_descriptors WHERE chat_id = ? AND lower(cardinality) IN ('noise', 'generic', 'ignore');",
                (chat_id,)
            )
            for r in cur.fetchall():
                if r[0]:
                    custom_noise.add(r[0].strip().lower())
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
            if filter_noise and is_noise_candidate(m, participants, custom_noise):
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
    displayed_candidates = serialized_mentions

    shard_info = None
    if shard and "/" in shard:
        try:
            parts = shard.strip().split("/")
            s_idx = int(parts[0])
            s_total = int(parts[1])
            if 1 <= s_idx <= s_total:
                chunk_size = (total_candidates + s_total - 1) // s_total
                start_i = (s_idx - 1) * chunk_size
                end_i = min(start_i + chunk_size, total_candidates)
                displayed_candidates = serialized_mentions[start_i:end_i]
                shard_info = {
                    "shard_index": s_idx,
                    "total_shards": s_total,
                    "shard_start": start_i + 1,
                    "shard_end": end_i,
                    "shard_size": len(displayed_candidates),
                    "total_candidates": total_candidates
                }
        except Exception:
            pass

    page_info = None
    if not shard_info and page_size and page_size > 0:
        total_pages = max(1, (total_candidates + page_size - 1) // page_size)
        cur_page = max(1, min(page, total_pages))
        start_i = (cur_page - 1) * page_size
        end_i = min(start_i + page_size, total_candidates)
        displayed_candidates = serialized_mentions[start_i:end_i]
        page_info = {
            "current_page": cur_page,
            "total_pages": total_pages,
            "page_size": page_size,
            "page_start": start_i + 1,
            "page_end": end_i,
            "total_candidates": total_candidates
        }
    elif not shard_info and limit and limit > 0:
        displayed_candidates = serialized_mentions[:limit]

    return {
        "chat_id": chat_id,
        "total_mentions": sum(m["count"] for m in serialized_mentions),
        "unique_candidate_names": total_candidates,
        "filtered_noise": filter_noise,
        "custom_noise_count": len(custom_noise),
        "min_count": min_count,
        "limit": limit,
        "page_info": page_info,
        "shard_info": shard_info,
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
    shard_info = data.get("shard_info")
    page_info = data.get("page_info")
    limit_val = data.get("limit")

    badge = ""
    if shard_info:
        badge = f" [Shard {shard_info['shard_index']}/{shard_info['total_shards']} (items {shard_info['shard_start']}–{shard_info['shard_end']} of {total_names})]"
    elif page_info:
        badge = f" [Page {page_info['current_page']}/{page_info['total_pages']} (items {page_info['page_start']}–{page_info['page_end']} of {total_names})]"
    elif limit_val and len(candidates) < total_names:
        badge = f" [Showing top {len(candidates)} of {total_names}]"

    c_label = f" [Chat: {chat_name or data.get('chat_id', '')}]"
    print("\n" + "=" * 80)
    print(f"👥 EXTRACTED CANDIDATE ENTITIES (SCALEDOWN EXTRACTION SUMMARY){c_label}{badge}")
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
    if shard_info or page_info or (limit_val and len(candidates) < total_names):
        print("⚠️  WARNING / DO NOT DISCARD REMAINING CANDIDATES:")
        print("   All candidates across shards must be screened for legitimate individuals vs noise.")
        print("   To screen all candidates without context flooding, dispatch `candidate-triage` subagents per shard:")
        print(f"   python3 project/scripts/query_chat.py -C {data.get('chat_id')} --candidates --candidates-shard 1/4 --json")
        print("-" * 80)
    print("💡 SUPERVISOR ACTION:")
    print("   1. Dispatch `candidate-triage` subagents on candidate shards to select legitimate third parties.")
    print("   2. Register custom noise words if needed via: --add-noise-word \"term1,term2\"")
    print("   3. Group vetted candidates into 2-3 person clusters for `entity-investigator` subagents.")
    print("=" * 80 + "\n")
