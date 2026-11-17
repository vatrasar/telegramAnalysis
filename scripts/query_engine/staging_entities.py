"""Staging table and review workflow for third-party candidate entities."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from .entities import ensure_entities_tables, register_entity, get_chat_entities


def ensure_staging_tables(conn: sqlite3.Connection) -> None:
    """Ensure staging_entities and entity_disambiguation_pairs tables exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS staging_entities (
        staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        proposed_name TEXT NOT NULL,
        proposed_role TEXT,
        anchors TEXT,
        context_notes TEXT,
        source_thread_id TEXT,
        proposed_by TEXT NOT NULL DEFAULT 'entity-investigator',
        status TEXT NOT NULL DEFAULT 'pending',
        reviewed_at TEXT,
        resolution_notes TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_staging_entities_chat_status ON staging_entities(chat_id, status);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS entity_disambiguation_pairs (
        chat_id TEXT NOT NULL,
        entity_a TEXT NOT NULL,
        entity_b TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'verified_distinct',
        audited_at TEXT NOT NULL,
        reason TEXT,
        PRIMARY KEY (chat_id, entity_a, entity_b)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_disambiguation_pairs_chat ON entity_disambiguation_pairs(chat_id);")
    conn.commit()


def stage_entity(
    db_path: str,
    chat_id: str,
    name: str,
    role: Optional[str] = None,
    desc: Optional[str] = None,
    thread_id: Optional[str] = None,
    proposed_by: str = "entity-investigator"
) -> Dict[str, Any]:
    """Insert a single proposed candidate entity into staging."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute("""
    INSERT INTO staging_entities (
        chat_id, proposed_name, proposed_role, anchors, context_notes,
        source_thread_id, proposed_by, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?);
    """, (chat_id, name.strip(), role.strip() if role else None, None, desc.strip() if desc else None,
          thread_id.strip() if thread_id else None, proposed_by, now_iso))
    staging_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "staged",
        "staging_id": staging_id,
        "chat_id": chat_id,
        "proposed_name": name,
        "proposed_role": role,
        "thread_id": thread_id
    }


def stage_entities_batch(
    db_path: str,
    chat_id: str,
    raw_payload: str,
    thread_id: Optional[str] = None,
    proposed_by: str = "entity-investigator"
) -> Dict[str, Any]:
    """Insert a batch (JSON array) of proposed candidate entities into staging."""
    try:
        entities = json.loads(raw_payload)
    except Exception as e:
        return {"error": f"Invalid JSON payload for --stage-entities-batch: {e}"}

    if isinstance(entities, dict):
        entities = entities.get("entities", [])
    if not isinstance(entities, list):
        return {"error": "Payload must be a JSON array of entities or an object with 'entities' array."}

    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    staged_items = []
    for item in entities:
        if not isinstance(item, dict):
            continue
        p_name = item.get("name") or item.get("proposed_name") or item.get("resolved_name") or item.get("mention")
        if not p_name:
            continue
        p_role = item.get("role") or item.get("verified_role") or item.get("proposed_role")
        p_desc = item.get("desc") or item.get("context") or item.get("notes")
        anchors = item.get("anchors")
        if isinstance(anchors, list):
            anchors_str = "; ".join(anchors)
        else:
            anchors_str = str(anchors) if anchors else None

        t_id = item.get("thread_id") or thread_id

        cur.execute("""
        INSERT INTO staging_entities (
            chat_id, proposed_name, proposed_role, anchors, context_notes,
            source_thread_id, proposed_by, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?);
        """, (chat_id, str(p_name).strip(), str(p_role).strip() if p_role else None,
              anchors_str, str(p_desc).strip() if p_desc else None,
              str(t_id).strip() if t_id else None, proposed_by, now_iso))
        staged_items.append({"staging_id": cur.lastrowid, "name": p_name, "role": p_role})

    conn.commit()
    conn.close()

    return {
        "status": "staged_batch",
        "chat_id": chat_id,
        "staged_count": len(staged_items),
        "items": staged_items
    }


def get_pending_staging_entities(db_path: str, chat_id: str) -> List[Dict[str, Any]]:
    """Retrieve all candidate entities currently pending supervisor review."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()

    cur.execute("""
    SELECT staging_id, chat_id, proposed_name, proposed_role, anchors,
           context_notes, source_thread_id, proposed_by, status, created_at
    FROM staging_entities
    WHERE chat_id = ? AND status = 'pending'
    ORDER BY staging_id ASC;
    """, (chat_id,))
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "staging_id": r[0],
            "chat_id": r[1],
            "proposed_name": r[2],
            "proposed_role": r[3],
            "anchors": r[4],
            "context_notes": r[5],
            "source_thread_id": r[6],
            "proposed_by": r[7],
            "status": r[8],
            "created_at": r[9]
        })
    return results


def approve_staging_entity(
    db_path: str,
    chat_id: str,
    staging_id: int,
    canonical_name: Optional[str] = None,
    role: Optional[str] = None,
    desc: Optional[str] = None,
    is_ex: bool = False,
    is_romantic: bool = False
) -> Dict[str, Any]:
    """Approve a staged entity and register it in chat_entities."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT proposed_name, proposed_role, anchors, context_notes, status FROM staging_entities WHERE staging_id = ? AND chat_id = ?;",
                (staging_id, chat_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"error": f"Staging entity {staging_id} not found for chat {chat_id}."}

    p_name, p_role, p_anchors, p_context, cur_status = row
    final_name = canonical_name.strip() if canonical_name else p_name
    final_role = role.strip() if role else p_role

    combined_desc = []
    if desc:
        combined_desc.append(desc.strip())
    if p_anchors:
        combined_desc.append(f"Anchors: {p_anchors}")
    if p_context and (not desc or p_context not in desc):
        combined_desc.append(f"Context: {p_context}")
    final_desc = "; ".join(combined_desc) if combined_desc else None

    # Register into main chat_entities
    reg_res = register_entity(
        conn=conn,
        chat_id=chat_id,
        name=final_name,
        role=final_role,
        descriptors=final_desc,
        is_ex=is_ex,
        is_romantic=is_romantic,
        notes=final_desc
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    resolution = f"Approved as '{final_name}' (role: {final_role})"
    cur.execute("""
    UPDATE staging_entities
    SET status = 'approved', reviewed_at = ?, resolution_notes = ?
    WHERE staging_id = ?;
    """, (now_iso, resolution, staging_id))
    conn.commit()
    conn.close()

    return {
        "status": "approved",
        "staging_id": staging_id,
        "registered_entity": reg_res,
        "resolution": resolution
    }


def merge_staging_entity(
    db_path: str,
    chat_id: str,
    staging_id: int,
    into_entity: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Merge a staged proposal into an existing registered entity as an alias/anchor."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT proposed_name, proposed_role, anchors, context_notes, status FROM staging_entities WHERE staging_id = ? AND chat_id = ?;",
                (staging_id, chat_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"error": f"Staging entity {staging_id} not found for chat {chat_id}."}

    p_name, p_role, p_anchors, p_context, cur_status = row

    # Find existing target entity
    target_clean = into_entity.strip().lower()
    cur.execute("SELECT entity_id, name_or_alias, associated_descriptors, notes FROM chat_entities WHERE chat_id = ?;", (chat_id,))
    target_row = None
    for r in cur.fetchall():
        if r[0].lower() == target_clean or r[1].lower() == target_clean:
            target_row = r
            break

    if not target_row:
        conn.close()
        return {"error": f"Target entity '{into_entity}' not found in chat_entities for chat {chat_id}."}

    tgt_id, tgt_name, tgt_desc, tgt_notes = target_row
    now_iso = datetime.now(timezone.utc).isoformat()

    add_details = f"Merged alias '{p_name}'"
    if p_anchors:
        add_details += f" ({p_anchors})"
    if reason:
        add_details += f": {reason}"

    updated_notes = (tgt_notes or "") + (f"; {add_details}" if tgt_notes else add_details)
    cur.execute("UPDATE chat_entities SET notes = ?, updated_at = ? WHERE entity_id = ? AND chat_id = ?;",
                (updated_notes, now_iso, tgt_id, chat_id))

    resolution = f"Merged into '{tgt_name}': {add_details}"
    cur.execute("""
    UPDATE staging_entities
    SET status = 'merged', reviewed_at = ?, resolution_notes = ?
    WHERE staging_id = ?;
    """, (now_iso, resolution, staging_id))
    conn.commit()
    conn.close()

    return {
        "status": "merged",
        "staging_id": staging_id,
        "merged_into": tgt_name,
        "resolution": resolution
    }


def reject_staging_entity(
    db_path: str,
    chat_id: str,
    staging_id: int,
    reason: str
) -> Dict[str, Any]:
    """Reject a staged proposal as transactional noise, episodic bystander, or false positive."""
    if not reason or not reason.strip():
        return {"error": "Rejection requires an explicit reason (e.g. 'episodic bystander', 'transactional worker', 'false alarm')."}

    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT proposed_name, status FROM staging_entities WHERE staging_id = ? AND chat_id = ?;",
                (staging_id, chat_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"error": f"Staging entity {staging_id} not found for chat {chat_id}."}

    now_iso = datetime.now(timezone.utc).isoformat()
    resolution = f"Rejected: {reason.strip()}"
    cur.execute("""
    UPDATE staging_entities
    SET status = 'rejected', reviewed_at = ?, resolution_notes = ?
    WHERE staging_id = ?;
    """, (now_iso, resolution, staging_id))
    conn.commit()
    conn.close()

    return {
        "status": "rejected",
        "staging_id": staging_id,
        "proposed_name": row[0],
        "resolution": resolution
    }


def record_distinct_pair(
    db_path: str,
    chat_id: str,
    entity_a: str,
    entity_b: str,
    reason: str
) -> Dict[str, Any]:
    """Record an audited distinct entity pair, persisting negative boundaries in notes and pair cache."""
    if not reason or not reason.strip():
        return {"error": "Recording a distinct pair requires an explicit reason with evidence anchors."}

    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    ensure_staging_tables(conn)
    cur = conn.cursor()

    cur.execute("SELECT entity_id, name_or_alias, notes, associated_descriptors FROM chat_entities WHERE chat_id = ?;", (chat_id,))
    rows = cur.fetchall()

    def find_ent(target: str) -> Optional[Tuple[str, str, str, str]]:
        t = target.strip().lower()
        for r in rows:
            if r[0].lower() == t or r[1].lower() == t:
                return r
        return None

    ent_1 = find_ent(entity_a)
    ent_2 = find_ent(entity_b)

    if not ent_1:
        conn.close()
        return {"error": f"Entity '{entity_a}' not found in chat_entities for chat {chat_id}."}
    if not ent_2:
        conn.close()
        return {"error": f"Entity '{entity_b}' not found in chat_entities for chat {chat_id}."}

    id1, name1, notes1, desc1 = ent_1
    id2, name2, notes2, desc2 = ent_2

    if id1 == id2:
        conn.close()
        return {"error": "Cannot record an entity as distinct from itself."}

    now_iso = datetime.now(timezone.utc).isoformat()
    reason_clean = reason.strip()

    # Append negative boundary to Entity 1
    boundary_1 = f"NOT {name2} (Audited distinct: {reason_clean})"
    updated_notes_1 = (notes1 or "") + (f"; {boundary_1}" if notes1 else boundary_1)
    cur.execute("UPDATE chat_entities SET notes = ?, updated_at = ? WHERE entity_id = ? AND chat_id = ?;",
                (updated_notes_1, now_iso, id1, chat_id))

    # Append negative boundary to Entity 2
    boundary_2 = f"NOT {name1} (Audited distinct: {reason_clean})"
    updated_notes_2 = (notes2 or "") + (f"; {boundary_2}" if notes2 else boundary_2)
    cur.execute("UPDATE chat_entities SET notes = ?, updated_at = ? WHERE entity_id = ? AND chat_id = ?;",
                (updated_notes_2, now_iso, id2, chat_id))

    # Persist in entity_disambiguation_pairs (canonical alphabetic order)
    pair_a, pair_b = sorted([name1, name2])
    cur.execute("""
    INSERT INTO entity_disambiguation_pairs (chat_id, entity_a, entity_b, status, audited_at, reason)
    VALUES (?, ?, ?, 'verified_distinct', ?, ?)
    ON CONFLICT(chat_id, entity_a, entity_b) DO UPDATE SET
        status = 'verified_distinct', audited_at = ?, reason = ?;
    """, (chat_id, pair_a, pair_b, now_iso, reason_clean, now_iso, reason_clean))

    conn.commit()
    conn.close()

    return {
        "status": "distinct_pair_recorded",
        "chat_id": chat_id,
        "entity_1": name1,
        "entity_2": name2,
        "negative_boundary_1": boundary_1,
        "negative_boundary_2": boundary_2,
        "reason": reason_clean
    }
