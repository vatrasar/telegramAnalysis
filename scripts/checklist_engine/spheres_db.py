"""Database operations for the Life Spheres Checklist."""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from checklist_engine.spheres_def import CHECKLIST_DEFINITIONS, VALID_STATUSES


def ensure_checklist_table(conn: sqlite3.Connection):
    """Create the life_spheres_checklist and metadata tables and indexes if they do not exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS life_spheres_checklist (
        chat_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        sphere_id TEXT NOT NULL,
        sphere_name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_item TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        evidence_summary TEXT,
        query_terms_used TEXT,
        semantic_queries_used TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, item_id)
    );
    """)
    # Auto-migration if table already exists without semantic_queries_used
    cur.execute("PRAGMA table_info(life_spheres_checklist);")
    columns = [col[1] for col in cur.fetchall()]
    if "semantic_queries_used" not in columns:
        cur.execute("ALTER TABLE life_spheres_checklist ADD COLUMN semantic_queries_used TEXT;")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_status ON life_spheres_checklist(chat_id, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_sphere ON life_spheres_checklist(chat_id, sphere_id);")
    conn.commit()


def is_checklist_waived(conn: sqlite3.Connection, chat_id: str) -> Tuple[bool, Optional[str]]:
    """Check if the checklist is currently flagged as waived/exempt in metadata."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"checklist_mode_{chat_id}",))
        row = cur.fetchone()
        if row and row[0] == "waived":
            cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"checklist_waiver_reason_{chat_id}",))
            r_row = cur.fetchone()
            reason = r_row[0] if r_row else "Ad-hoc task / partial inquiry (full profiling not required)"
            return True, reason
    except Exception:
        pass
    return False, None


def waive_checklist(conn: sqlite3.Connection, chat_id: str, reason: str = "Ad-hoc task / partial inquiry") -> int:
    """Waive/disable the checklist for a chat by setting all pending items to 'not_applicable'."""
    ensure_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now().isoformat()

    cur.execute("""
    INSERT INTO metadata (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
    """, (f"checklist_mode_{chat_id}", "waived"))
    cur.execute("""
    INSERT INTO metadata (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
    """, (f"checklist_waiver_reason_{chat_id}", reason))

    notes = f"Exempt/Waived: {reason}"
    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = 'not_applicable', evidence_summary = ?, updated_at = ?
    WHERE chat_id = ? AND status = 'pending';
    """, (notes, now_iso, chat_id))
    waived_count = cur.rowcount
    conn.commit()
    return waived_count


def enable_checklist(conn: sqlite3.Connection, chat_id: str) -> int:
    """Re-enable the checklist for full profiling: removes waiver from metadata."""
    ensure_checklist_table(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM metadata WHERE key IN (?, ?);", (f"checklist_mode_{chat_id}", f"checklist_waiver_reason_{chat_id}"))
    now_iso = datetime.now().isoformat()
    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = 'pending', evidence_summary = '', updated_at = ?
    WHERE chat_id = ? AND status = 'not_applicable';
    """, (now_iso, chat_id))
    re_enabled = cur.rowcount
    conn.commit()
    return re_enabled


def resolve_chat_id(conn: sqlite3.Connection, chat_arg: Optional[str]) -> str:
    """Resolve explicit chat_id or automatically determine if only one chat exists."""
    cur = conn.cursor()
    if chat_arg:
        cur.execute("SELECT chat_id FROM chats WHERE chat_id = ? OR chat_name = ?;", (chat_arg, chat_arg))
        row = cur.fetchone()
        if row:
            return row[0]
        return chat_arg

    cur.execute("SELECT chat_id, chat_name FROM chats;")
    rows = cur.fetchall()
    if not rows:
        raise ValueError("No chats found in database. Ingest chat logs first via db_builder.py.")
    if len(rows) == 1:
        return rows[0][0]

    names = ", ".join(f"{r[0]} ('{r[1]}')" for r in rows)
    raise ValueError(
        f"Multiple chats found in database ({names}).\n"
        f"Please specify --chat <chat_id> to audit a specific chat, "
        f"or --chat global (or --chat <subject_name>) for a cross-chat personality profile."
    )


def init_checklist(conn: sqlite3.Connection, chat_id: str, reset: bool = False) -> Tuple[int, int]:
    """Initialize checklist items for a chat. Returns (inserted_count, total_count)."""
    ensure_checklist_table(conn)
    cur = conn.cursor()

    if reset:
        cur.execute("DELETE FROM life_spheres_checklist WHERE chat_id = ?;", (chat_id,))
        conn.commit()

    cur.execute("SELECT item_id FROM life_spheres_checklist WHERE chat_id = ?;", (chat_id,))
    existing_ids = {r[0] for r in cur.fetchall()}

    now_iso = datetime.now().isoformat()
    inserted = 0

    for item in CHECKLIST_DEFINITIONS:
        if item["item_id"] not in existing_ids:
            cur.execute("""
            INSERT INTO life_spheres_checklist (
                chat_id, item_id, sphere_id, sphere_name, category, sub_item,
                description, status, evidence_summary, query_terms_used, semantic_queries_used, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', '', '', ?);
            """, (
                chat_id,
                item["item_id"],
                item["sphere_id"],
                item["sphere_name"],
                item["category"],
                item["sub_item"],
                item["description"],
                now_iso
            ))
            inserted += 1

    conn.commit()
    return inserted, len(CHECKLIST_DEFINITIONS)


def get_checklist_stats(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Compute completion statistics grouped by status and by sphere."""
    ensure_checklist_table(conn)
    cur = conn.cursor()

    is_waived, waiver_reason = is_checklist_waived(conn, chat_id)

    cur.execute("""
    SELECT status, count(*)
    FROM life_spheres_checklist
    WHERE chat_id = ?
    GROUP BY status;
    """, (chat_id,))
    status_counts = {r[0]: r[1] for r in cur.fetchall()}

    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    no_data = status_counts.get("no_data", 0)
    not_applicable = status_counts.get("not_applicable", 0)
    pending = status_counts.get("pending", 0)
    resolved = completed + no_data + not_applicable

    pct = (resolved / total * 100.0) if total > 0 else 0.0

    cur.execute("""
    SELECT count(*)
    FROM life_spheres_checklist
    WHERE chat_id = ? AND status IN ('completed', 'no_data')
      AND semantic_queries_used IS NOT NULL AND trim(semantic_queries_used) != '';
    """, (chat_id,))
    semantic_count = cur.fetchone()[0]
    substantive_resolved = completed + no_data
    semantic_pct = (semantic_count / substantive_resolved * 100.0) if substantive_resolved > 0 else 0.0

    cur.execute("""
    SELECT sphere_id, sphere_name, status, count(*)
    FROM life_spheres_checklist
    WHERE chat_id = ?
    GROUP BY sphere_id, sphere_name, status
    ORDER BY sphere_id;
    """, (chat_id,))
    sphere_rows = cur.fetchall()

    spheres: Dict[str, Dict[str, Any]] = {}
    for sid, sname, st, cnt in sphere_rows:
        if sid not in spheres:
            spheres[sid] = {
                "sphere_id": sid,
                "sphere_name": sname,
                "total": 0,
                "completed": 0,
                "no_data": 0,
                "not_applicable": 0,
                "pending": 0
            }
        spheres[sid]["total"] += cnt
        spheres[sid][st] = cnt

    for sid in spheres:
        s = spheres[sid]
        s_resolved = s["completed"] + s["no_data"] + s["not_applicable"]
        s["percent"] = (s_resolved / s["total"] * 100.0) if s["total"] > 0 else 0.0

    return {
        "chat_id": chat_id,
        "is_waived": is_waived,
        "waiver_reason": waiver_reason,
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "completed": completed,
        "no_data": no_data,
        "not_applicable": not_applicable,
        "percent": pct,
        "semantic_probed": semantic_count,
        "semantic_coverage_pct": semantic_pct,
        "is_complete": (pending == 0 and total > 0),
        "spheres": list(spheres.values())
    }


def update_checklist_item(
    conn: sqlite3.Connection,
    chat_id: str,
    item_id: str,
    status: str,
    notes: Optional[str] = None,
    queries: Optional[str] = None,
    semantic_queries: Optional[str] = None
) -> bool:
    """Update status, notes, query terms, and semantic vector queries for a specific checklist item."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid options: {', '.join(sorted(VALID_STATUSES))}")

    ensure_checklist_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT item_id, evidence_summary, query_terms_used, semantic_queries_used FROM life_spheres_checklist WHERE chat_id = ? AND item_id = ?;", (chat_id, item_id))
    row = cur.fetchone()
    if not row:
        return False

    old_notes = row[1] or ""
    old_queries = row[2] or ""
    old_semantic = row[3] or ""

    new_notes = notes if notes is not None else old_notes
    new_queries = queries if queries is not None else old_queries
    new_semantic = semantic_queries if semantic_queries is not None else old_semantic

    if semantic_queries is None and queries:
        if "--semantic" in queries or "semantic:" in queries.lower():
            if not new_semantic:
                new_semantic = queries

    now_iso = datetime.now().isoformat()

    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = ?, evidence_summary = ?, query_terms_used = ?, semantic_queries_used = ?, updated_at = ?
    WHERE chat_id = ? AND item_id = ?;
    """, (status, new_notes, new_queries, new_semantic, now_iso, chat_id, item_id))
    conn.commit()
    return True


def list_checklist_items(
    conn: sqlite3.Connection,
    chat_id: str,
    status_filter: Optional[str] = None,
    sphere_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List checklist items matching optional status and sphere filters."""
    ensure_checklist_table(conn)
    cur = conn.cursor()

    sql = """
    SELECT item_id, sphere_id, sphere_name, category, sub_item, description,
           status, evidence_summary, query_terms_used, semantic_queries_used, updated_at
    FROM life_spheres_checklist
    WHERE chat_id = ?
    """
    params: List[Any] = [chat_id]

    if status_filter:
        if status_filter == "resolved":
            sql += " AND status IN ('completed', 'no_data', 'not_applicable')"
        elif status_filter == "unresolved":
            sql += " AND status = 'pending'"
        elif status_filter in VALID_STATUSES:
            sql += " AND status = ?"
            params.append(status_filter)
        else:
            raise ValueError(f"Unknown status filter '{status_filter}'. Use: pending, completed, no_data, not_applicable, resolved, unresolved")

    if sphere_filter:
        clean_sf = sphere_filter.strip()
        if len(clean_sf) == 1:
            sql += " AND sphere_id = ?"
            params.append(clean_sf.upper())
        else:
            sql += " AND (sphere_id = ? OR sphere_name LIKE ?)"
            params.extend([clean_sf.upper(), f"%{clean_sf}%"])

    sql += " ORDER BY sphere_id, item_id;"
    cur.execute(sql, params)
    rows = cur.fetchall()

    return [
        {
            "item_id": r[0],
            "sphere_id": r[1],
            "sphere_name": r[2],
            "category": r[3],
            "sub_item": r[4],
            "description": r[5],
            "status": r[6],
            "evidence_summary": r[7] or "",
            "query_terms_used": r[8] or "",
            "semantic_queries_used": r[9] or "",
            "updated_at": r[10]
        }
        for r in rows
    ]
