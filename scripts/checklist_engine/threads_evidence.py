"""Evidence, manifest, and redundancy management for Thread Forensic Audit."""

import sys
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from checklist_engine.threads_db import ensure_thread_checklist_table


def export_delta_manifest(
    conn: sqlite3.Connection,
    chat_id: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Export concise manifest of pending threads with triage summaries and candidate entities."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0

    if has_triage:
        cur.execute("PRAGMA table_info(thread_triage);")
        tcols = {col[1] for col in cur.fetchall()}
        sum_col = "coalesce(tt.summary_short, 'No summary generated yet')" if "summary_short" in tcols else "'No summary generated yet'"
        ent_col = "coalesce(tt.candidate_entities, '[]')" if "candidate_entities" in tcols else "'[]'"

        sql = f"""
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               {sum_col}, {ent_col},
               substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        LEFT JOIN thread_triage tt ON tac.thread_id = tt.thread_id
        WHERE tac.chat_id = ? AND tac.status = 'pending'
        ORDER BY tac.salience_score DESC, tac.message_count DESC
        """
    else:
        sql = """
        SELECT tac.thread_id, tac.radar_sources, tac.salience_score, tac.primary_category,
               tac.start_date, tac.message_count, tac.total_words,
               'No summary generated yet', '[]',
               substr(t.dialogue_text, 1, 300)
        FROM thread_audit_checklist tac
        JOIN threads t ON tac.thread_id = t.thread_id
        WHERE tac.chat_id = ? AND tac.status = 'pending'
        ORDER BY tac.salience_score DESC, tac.message_count DESC
        """

    if limit:
        sql += f" LIMIT {int(limit)}"

    cur.execute(sql, (chat_id,))
    rows = cur.fetchall()

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", (f"delta_manifest_exported_{chat_id}", now_iso))
    conn.commit()

    manifest = []
    for r in rows:
        manifest.append({
            "thread_id": r[0],
            "radar_sources": r[1],
            "salience_score": r[2],
            "category": r[3],
            "date": r[4],
            "messages": r[5],
            "words": r[6],
            "summary": r[7],
            "candidate_entities": r[8],
            "sample_snippet": r[9].strip().replace("\n", " ") if r[9] else ""
        })
    return manifest


def resolve_redundant_threads(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_ids: List[str],
    reason: str
) -> int:
    """Safely resolve redundant/corroborating threads with full audit trail."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"delta_manifest_exported_{chat_id}",))
    row = cur.fetchone()
    if not row:
        print("\n[!] FRAUD / WORKFLOW VIOLATION: Cannot resolve redundant threads before exporting delta manifest!", file=sys.stderr)
        print("    You must first export the manifest for subagent review:", file=sys.stderr)
        print(f"      python3 project/scripts/thread_checklist.py -C {chat_id} --export-delta-manifest", file=sys.stderr)
        sys.exit(1)

    clean_reason = reason.strip() if reason else ""
    if not clean_reason or clean_reason == "Ad-hoc task / partial inquiry":
        print("\n[!] Error: You must provide a specific corroborating theme via --reason.\n", file=sys.stderr)
        sys.exit(1)

    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0
    for tid in thread_ids:
        cur.execute("""
        UPDATE thread_audit_checklist
        SET status = 'completed',
            findings_summary = 'Theoretical Saturation: Redundant discussion corroborating established baseline',
            notes = coalesce(notes || ' | ', '') || 'Corroborating: ' || ?,
            updated_at = ?
        WHERE chat_id = ? AND thread_id = ?;
        """, (clean_reason, now_iso, chat_id, tid))
        updated += cur.rowcount

    conn.commit()
    return updated


def export_audited_evidence(
    conn: sqlite3.Connection,
    chat_id: str,
    tag: Optional[str] = None,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Export completed/audited threads and evidence from thread_audit_checklist with optional tag/category filtering."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    sql = """
    SELECT thread_id, start_date, primary_category, radar_sources,
           findings_summary, key_quotes, thematic_tags, notes, updated_at,
           coalesce(target_agent, '') as target_agent,
           coalesce(target_chapter, '') as target_chapter
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'completed'
      AND (findings_summary IS NOT NULL AND findings_summary NOT LIKE 'Theoretical Saturation%'
           OR key_quotes IS NOT NULL)
    """
    params = [chat_id]
    if tag:
        sql += " AND (thematic_tags LIKE ? OR notes LIKE ?) "
        clean_tag = f"%{tag.strip()}%"
        params.extend([clean_tag, clean_tag])
    if category:
        sql += " AND (primary_category = ? OR target_chapter = ?) "
        params.extend([category.strip(), category.strip()])

    sql += " ORDER BY start_date ASC;"
    cur.execute(sql, params)
    rows = cur.fetchall()

    evidence = []
    for r in rows:
        evidence.append({
            "thread_id": r[0],
            "date": r[1],
            "category": r[2],
            "radars": r[3],
            "findings": r[4] or "",
            "quotes": r[5] or "",
            "tags": r[6] or "",
            "notes": r[7] or "",
            "updated_at": r[8],
            "target_agent": r[9] or "",
            "target_chapter": r[10] or ""
        })
    return evidence


def route_thread_evidence(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    target_agent: Optional[str] = None,
    target_chapter: Optional[str] = None,
    significance: Optional[str] = None,
    tags: Optional[str] = None
) -> Dict[str, Any]:
    """Route audited thread evidence to a target drafter agent and report chapter."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    updates = ["updated_at = ?"]
    params: List[Any] = [now_iso]

    if target_agent:
        updates.append("target_agent = ?")
        params.append(target_agent.strip())
    if target_chapter:
        updates.append("target_chapter = ?")
        params.append(target_chapter.strip())
    if tags:
        updates.append("thematic_tags = coalesce(thematic_tags || ' ', '') || ?")
        params.append(tags.strip())
    if significance:
        updates.append("notes = coalesce(notes || ' | ', '') || ?")
        params.append(f"Significance: {significance.strip()}")

    params.extend([chat_id, thread_id])
    sql = f"UPDATE thread_audit_checklist SET {', '.join(updates)} WHERE chat_id = ? AND thread_id = ?;"
    cur.execute(sql, params)
    updated = cur.rowcount
    conn.commit()

    return {
        "chat_id": chat_id,
        "thread_id": thread_id,
        "target_agent": target_agent,
        "target_chapter": target_chapter,
        "significance": significance,
        "success": updated > 0
    }


def get_evidence_for_target(
    conn: sqlite3.Connection,
    chat_id: str,
    target: str
) -> List[Dict[str, Any]]:
    """Retrieve audited evidence items routed specifically to a given agent role or chapter."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    clean_target = target.strip().lower()

    sql = """
    SELECT thread_id, start_date, primary_category, radar_sources,
           findings_summary, key_quotes, thematic_tags, notes, updated_at,
           coalesce(target_agent, '') as target_agent,
           coalesce(target_chapter, '') as target_chapter
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'completed'
      AND (
        lower(coalesce(target_agent, '')) = ?
        OR lower(coalesce(target_chapter, '')) = ?
        OR lower(coalesce(primary_category, '')) = ?
        OR lower(coalesce(thematic_tags, '')) LIKE ?
      )
    ORDER BY start_date ASC;
    """
    pattern = f"%{clean_target}%"
    cur.execute(sql, (chat_id, clean_target, clean_target, clean_target, pattern))
    rows = cur.fetchall()

    items = []
    for r in rows:
        items.append({
            "thread_id": r[0],
            "date": r[1],
            "category": r[2],
            "radars": r[3],
            "findings": r[4] or "",
            "quotes": r[5] or "",
            "tags": r[6] or "",
            "notes": r[7] or "",
            "updated_at": r[8],
            "target_agent": r[9],
            "target_chapter": r[10]
        })
    return items

