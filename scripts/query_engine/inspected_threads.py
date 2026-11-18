"""Thread inspection state tracking and reconnaissance catalog for query engine."""

import sqlite3
import datetime as dt_module
from typing import List, Dict, Any, Optional, Tuple


def ensure_inspected_threads_table(conn: sqlite3.Connection) -> None:
    """Ensure inspected_threads table and required indexes exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inspected_threads (
        chat_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        inspected_by TEXT NOT NULL,
        stage TEXT NOT NULL,
        findings_summary TEXT,
        thematic_tags TEXT,
        covered_spheres TEXT,
        inspected_at TEXT NOT NULL,
        coverage TEXT DEFAULT 'full',
        entities_detected TEXT,
        unresolved_pronouns TEXT,
        PRIMARY KEY (chat_id, thread_id)
    );
    """)
    cur.execute("PRAGMA table_info(inspected_threads);")
    cols = {c[1] for c in cur.fetchall()}
    if "coverage" not in cols:
        cur.execute("ALTER TABLE inspected_threads ADD COLUMN coverage TEXT DEFAULT 'full';")
    if "entities_detected" not in cols:
        cur.execute("ALTER TABLE inspected_threads ADD COLUMN entities_detected TEXT;")
    if "unresolved_pronouns" not in cols:
        cur.execute("ALTER TABLE inspected_threads ADD COLUMN unresolved_pronouns TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inspected_threads_chat ON inspected_threads(chat_id);")
    conn.commit()


def mark_thread_inspected(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    inspected_by: str = "agent",
    stage: str = "entity_discovery",
    findings: str = "",
    tags: str = "",
    spheres: str = "",
    coverage: str = "full",
    entities_detected: str = "",
    unresolved_pronouns: str = "",
) -> Dict[str, Any]:
    """Mark a thread as inspected/read so subsequent stages do not re-read it blindly."""
    ensure_inspected_threads_table(conn)
    cur = conn.cursor()
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    cur.execute("""
    INSERT INTO inspected_threads (
        chat_id, thread_id, inspected_by, stage, findings_summary, thematic_tags,
        covered_spheres, inspected_at, coverage, entities_detected, unresolved_pronouns
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, thread_id) DO UPDATE SET
        inspected_by = excluded.inspected_by,
        stage = excluded.stage,
        findings_summary = CASE
            WHEN length(coalesce(inspected_threads.findings_summary, '')) = 0 THEN excluded.findings_summary
            WHEN length(coalesce(excluded.findings_summary, '')) = 0 THEN inspected_threads.findings_summary
            WHEN instr(inspected_threads.findings_summary, excluded.findings_summary) > 0 THEN inspected_threads.findings_summary
            ELSE inspected_threads.findings_summary || ' | ' || excluded.findings_summary
        END,
        thematic_tags = coalesce(inspected_threads.thematic_tags || ',', '') || excluded.thematic_tags,
        covered_spheres = coalesce(inspected_threads.covered_spheres || ',', '') || excluded.covered_spheres,
        inspected_at = excluded.inspected_at,
        coverage = CASE
            WHEN inspected_threads.coverage = 'full' OR excluded.coverage = 'full' THEN 'full'
            ELSE 'partial'
        END,
        entities_detected = CASE
            WHEN length(coalesce(inspected_threads.entities_detected, '')) = 0 THEN excluded.entities_detected
            WHEN length(coalesce(excluded.entities_detected, '')) = 0 THEN inspected_threads.entities_detected
            WHEN instr(inspected_threads.entities_detected, excluded.entities_detected) > 0 THEN inspected_threads.entities_detected
            ELSE inspected_threads.entities_detected || '; ' || excluded.entities_detected
        END,
        unresolved_pronouns = coalesce(inspected_threads.unresolved_pronouns || '; ', '') || excluded.unresolved_pronouns;
    """, (chat_id, thread_id, inspected_by, stage, findings, tags, spheres, now_iso, coverage, entities_detected, unresolved_pronouns))

    # Also synchronize with thread_audit_checklist if table exists
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_audit_checklist';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        UPDATE thread_audit_checklist
        SET status = CASE WHEN status = 'pending' THEN 'completed' ELSE status END,
            findings_summary = coalesce(findings_summary || ' | ', '') || ?,
            updated_at = ?
        WHERE chat_id = ? AND thread_id = ?;
        """, (f"[Inspected in {stage} by {inspected_by}] {findings}".strip(), now_iso, chat_id, thread_id))

    conn.commit()
    return {
        "status": "success",
        "chat_id": chat_id,
        "thread_id": thread_id,
        "inspected_by": inspected_by,
        "stage": stage,
        "coverage": coverage,
        "entities_detected": entities_detected,
        "unresolved_pronouns": unresolved_pronouns,
        "covered_spheres": spheres,
        "inspected_at": now_iso,
    }


def get_inspected_threads(
    conn: sqlite3.Connection,
    chat_id: str,
    sphere_id: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve catalog of threads inspected in the database."""
    ensure_inspected_threads_table(conn)
    cur = conn.cursor()
    sql = """
    SELECT thread_id, inspected_by, stage, findings_summary, thematic_tags, covered_spheres, inspected_at
    FROM inspected_threads
    WHERE chat_id = ?
    """
    params: List[Any] = [chat_id]
    if sphere_id:
        sql += " AND (covered_spheres LIKE ? OR covered_spheres LIKE ?)"
        params.extend([f"%{sphere_id}%", f"%{sphere_id.upper()}%"])
    if tag:
        sql += " AND thematic_tags LIKE ?"
        params.append(f"%{tag}%")
    sql += " ORDER BY inspected_at DESC;"

    cur.execute(sql, params)
    rows = cur.fetchall()
    results = []
    for r in rows:
        results.append({
            "thread_id": r[0],
            "inspected_by": r[1],
            "stage": r[2],
            "findings_summary": r[3] or "",
            "thematic_tags": r[4] or "",
            "covered_spheres": r[5] or "",
            "inspected_at": r[6],
        })
    return results


def is_thread_inspected(conn: sqlite3.Connection, chat_id: str, thread_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if a specific thread has already been inspected."""
    ensure_inspected_threads_table(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT inspected_by, stage, findings_summary, thematic_tags, covered_spheres, inspected_at,
           coverage, entities_detected, unresolved_pronouns
    FROM inspected_threads
    WHERE chat_id = ? AND thread_id = ?;
    """, (chat_id, thread_id))
    row = cur.fetchone()
    if row:
        return True, {
            "inspected_by": row[0],
            "stage": row[1],
            "findings_summary": row[2] or "",
            "thematic_tags": row[3] or "",
            "covered_spheres": row[4] or "",
            "inspected_at": row[5],
            "coverage": row[6] or "full",
            "entities_detected": row[7] or "",
            "unresolved_pronouns": row[8] or "",
        }
    return False, None


def print_inspected_threads(threads: List[Dict[str, Any]], chat_id: str) -> None:
    """Pretty print inspected threads catalog in terminal format."""
    print("\n" + "=" * 80)
    print(f"🔍 INSPECTED THREADS RECONNAISSANCE CATALOG (Chat: {chat_id})")
    print(f"Total Inspected: {len(threads)} threads")
    print("=" * 80)

    if not threads:
        print("  (No threads marked as inspected yet)")
        print("=" * 80 + "\n")
        return

    print(f"{'Thread ID':<12} {'Stage':<18} {'Inspector':<20} {'Spheres':<10} {'Inspected At'}")
    print("-" * 80)
    for t in threads:
        sph = t.get("covered_spheres") or "-"
        print(f"{t['thread_id']:<12} {t['stage']:<18} {t['inspected_by']:<20} {sph:<10} {t['inspected_at'][:16]}")
        if t.get("findings_summary"):
            summary_snippet = t['findings_summary'][:75] + ("..." if len(t['findings_summary']) > 75 else "")
            print(f"  ↳ Findings: {summary_snippet}")
    print("=" * 80 + "\n")
