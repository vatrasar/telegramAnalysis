"""Automatic volume assessment and thread sharding for entities and life spheres."""

import json
import sqlite3
from typing import Dict, Any, List, Optional


def find_entity_threads(conn: sqlite3.Connection, chat_id: str, entity_name: str) -> List[Dict[str, Any]]:
    """Find all threads associated with an entity name or alias, sorted chronologically."""
    cur = conn.cursor()
    aliases = {entity_name.strip()}
    cur.execute("""
    SELECT name_or_alias, associated_descriptors FROM chat_entities
    WHERE chat_id = ? AND (lower(name_or_alias) = lower(?) OR lower(associated_descriptors) LIKE ?)
    """, (chat_id, entity_name.strip(), f"%{entity_name.lower().strip()}%"))
    for row in cur.fetchall():
        if row[0]:
            aliases.add(row[0].strip())
        if row[1]:
            for desc in row[1].split(","):
                d = desc.strip()
                if d and len(d) > 2:
                    aliases.add(d)

    thread_ids = set()

    # 1. Check thread_triage candidate_entities
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] > 0:
        cur.execute(
            "SELECT thread_id, candidate_entities FROM thread_triage WHERE chat_id = ? AND candidate_entities IS NOT NULL",
            (chat_id,)
        )
        for tid, cand in cur.fetchall():
            cand_lower = cand.lower()
            if any(a.lower() in cand_lower for a in aliases):
                thread_ids.add(tid)

    # 2. Check inspected_threads entities_detected
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='inspected_threads';")
    if cur.fetchone()[0] > 0:
        cur.execute(
            "SELECT thread_id, entities_detected FROM inspected_threads WHERE chat_id = ? AND entities_detected IS NOT NULL",
            (chat_id,)
        )
        for tid, ents in cur.fetchall():
            ents_lower = ents.lower()
            if any(a.lower() in ents_lower for a in aliases):
                thread_ids.add(tid)

    # 3. Check chat_facts
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chat_facts';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT DISTINCT fact_thread FROM chat_facts
        WHERE chat_id = ? AND fact_thread IS NOT NULL AND (
            lower(entity_name) = lower(?) OR lower(fact_text) LIKE ? OR lower(quote) LIKE ?
        )
        """, (chat_id, entity_name, f"%{entity_name.lower()}%", f"%{entity_name.lower()}%"))
        for row in cur.fetchall():
            if row[0]:
                thread_ids.add(row[0])

    # 4. Check if entity is a chat participant / interlocutor
    cur.execute("""
    SELECT DISTINCT thread_id FROM threads
    WHERE chat_id = ? AND (lower(participants) LIKE ? OR lower(initiator) LIKE ?)
    """, (chat_id, f"%{entity_name.lower().strip()}%", f"%{entity_name.lower().strip()}%"))
    for row in cur.fetchall():
        if row[0]:
            thread_ids.add(row[0])

    # 5. Check FTS for entity mentions in text
    clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in entity_name).strip()
    if clean_q:
        fts_term = f'"{clean_q}"'
        try:
            cur.execute("""
            SELECT DISTINCT thread_id FROM messages_fts
            WHERE chat_id = ? AND messages_fts MATCH ?
            LIMIT 100
            """, (chat_id, fts_term))
            for row in cur.fetchall():
                if row[0]:
                    thread_ids.add(row[0])
        except Exception:
            pass

    if not thread_ids:
        return []

    placeholders = ",".join("?" for _ in thread_ids)
    sql = f"""
    SELECT thread_id, start_date, end_date, message_count, initiator
    FROM threads
    WHERE chat_id = ? AND thread_id IN ({placeholders})
    ORDER BY start_date ASC
    """
    cur.execute(sql, [chat_id] + list(thread_ids))
    rows = cur.fetchall()
    return [
        {
            "thread_id": r[0],
            "start_date": r[1],
            "end_date": r[2],
            "message_count": r[3],
            "initiator": r[4]
        }
        for r in rows
    ]


def find_sphere_threads(conn: sqlite3.Connection, chat_id: str, sphere_letter: str) -> List[Dict[str, Any]]:
    """Find all threads associated with a life sphere letter, sorted chronologically."""
    cur = conn.cursor()
    sphere_letter = sphere_letter.strip().upper()
    thread_ids = set()

    # 1. From chat_facts
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chat_facts';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT DISTINCT fact_thread FROM chat_facts
        WHERE chat_id = ? AND fact_thread IS NOT NULL AND upper(sphere_letter) = ?
        """, (chat_id, sphere_letter))
        for row in cur.fetchall():
            if row[0]:
                thread_ids.add(row[0])

    # 2. From inspected_threads
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='inspected_threads';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT thread_id FROM inspected_threads
        WHERE chat_id = ? AND covered_spheres IS NOT NULL AND upper(covered_spheres) LIKE ?
        """, (chat_id, f"%{sphere_letter}%"))
        for row in cur.fetchall():
            if row[0]:
                thread_ids.add(row[0])

    # 3. From thread_checklist
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_checklist';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT thread_id FROM thread_checklist
        WHERE chat_id = ? AND (upper(thematic_tags) LIKE ? OR upper(findings) LIKE ?)
        """, (chat_id, f"%SPHERE_{sphere_letter}%", f"%SPHERE_{sphere_letter}%"))
        for row in cur.fetchall():
            if row[0]:
                thread_ids.add(row[0])

    if not thread_ids:
        return []

    placeholders = ",".join("?" for _ in thread_ids)
    sql = f"""
    SELECT thread_id, start_date, end_date, message_count, initiator
    FROM threads
    WHERE chat_id = ? AND thread_id IN ({placeholders})
    ORDER BY start_date ASC
    """
    cur.execute(sql, [chat_id] + list(thread_ids))
    rows = cur.fetchall()
    return [
        {
            "thread_id": r[0],
            "start_date": r[1],
            "end_date": r[2],
            "message_count": r[3],
            "initiator": r[4]
        }
        for r in rows
    ]


def build_shards_from_threads(threads: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
    """Build chronological shards from a list of sorted threads."""
    if not threads:
        return []
    shards = []
    for i in range(0, len(threads), batch_size):
        chunk = threads[i:i + batch_size]
        s_date = (chunk[0]["start_date"] or "unknown")[:10]
        e_date = (chunk[-1]["end_date"] or chunk[-1]["start_date"] or "unknown")[:10]
        label = f"{s_date} to {e_date}" if s_date != e_date else s_date
        shards.append({
            "shard_id": len(shards) + 1,
            "label": label,
            "thread_count": len(chunk),
            "threads": [t["thread_id"] for t in chunk]
        })
    return shards


def shard_entity(db_path: str, chat_id: str, entity_name: str, batch_size: int = 5) -> Dict[str, Any]:
    """Assess thread volume for an entity and return chronological shards."""
    conn = sqlite3.connect(db_path)
    threads = find_entity_threads(conn, chat_id, entity_name)
    conn.close()

    total = len(threads)
    is_split = total > (batch_size + 1)
    shards = build_shards_from_threads(threads, batch_size=batch_size)

    return {
        "target": entity_name,
        "target_type": "entity",
        "chat_id": chat_id,
        "total_threads": total,
        "batch_size": batch_size,
        "status": "SPLIT_REQUIRED" if is_split else "SINGLE_WORKER",
        "recommended_shards": len(shards) if is_split else (1 if total > 0 else 0),
        "shards": shards
    }


def shard_sphere(db_path: str, chat_id: str, sphere_letter: str, batch_size: int = 5) -> Dict[str, Any]:
    """Assess thread volume for a life sphere and return chronological shards."""
    conn = sqlite3.connect(db_path)
    threads = find_sphere_threads(conn, chat_id, sphere_letter)
    conn.close()

    total = len(threads)
    is_split = total > (batch_size + 1)
    shards = build_shards_from_threads(threads, batch_size=batch_size)

    return {
        "target": sphere_letter.upper(),
        "target_type": "sphere",
        "chat_id": chat_id,
        "total_threads": total,
        "batch_size": batch_size,
        "status": "SPLIT_REQUIRED" if is_split else "SINGLE_WORKER",
        "recommended_shards": len(shards) if is_split else (1 if total > 0 else 0),
        "shards": shards
    }


def print_sharding_report(data: Dict[str, Any], json_output: bool = False) -> None:
    """Print volume assessment and sharding report."""
    if json_output:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    target = data.get("target", "Unknown")
    t_type = data.get("target_type", "target")
    total = data.get("total_threads", 0)
    status = data.get("status", "SINGLE_WORKER")
    shards = data.get("shards", [])
    batch_size = data.get("batch_size", 5)

    print("=" * 80)
    print(f"VOLUME ASSESSMENT & SHARDING REPORT: {target} ({t_type.upper()})")
    print(f"Chat ID: {data.get('chat_id')} | Total Associated Threads: {total}")
    status_str = f"[{status}]"
    if status == "SPLIT_REQUIRED":
        print(f"Status: {status_str} -> Exceeds single worker capacity (>{batch_size+1} threads).")
        print(f"Recommended Shards: {len(shards)} (Chronological batch size: {batch_size})")
    else:
        print(f"Status: {status_str} -> Optimal for single worker (<= {batch_size+1} threads).")
    print("=" * 80)

    if not shards:
        print("  No substantive associated dialogue threads found in database.")
    else:
        for s in shards:
            t_ids = ", ".join(s["threads"])
            print(f"  [Shard {s['shard_id']}] ({s['label']}) - {s['thread_count']} threads:")
            print(f"    Threads: {t_ids}")

    print("-" * 80)
    if status == "SPLIT_REQUIRED":
        print("WORKER ACTION GUIDANCE (Subagent Self-Scaling):")
        print(f"  1. DO NOT read all {total} threads into your primary context.")
        print(f"  2. Dispatch {len(shards)} worker subagents (TypeName: forensic-thread-investigator) in parallel.")
        print("  3. Assign one shard (up to 5 threads) to each worker.")
        print("  4. Workers extract anchored quotes and chronological dynamics.")
        print("  5. Synthesize final dossier/section directly from returned shard summaries.")
    else:
        print("WORKER ACTION GUIDANCE:")
        print("  Single worker capacity verified. Proceed to investigate threads directly.")
    print("=" * 80)
