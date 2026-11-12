"""Database operations for Thread Forensic Audit Checklist (Track B)."""

import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

VALID_STATUSES = {"pending", "completed", "skipped", "not_applicable"}
RESOLVED_STATUSES = {"completed", "skipped", "not_applicable"}


def ensure_thread_checklist_table(conn: sqlite3.Connection):
    """Create thread_audit_checklist and metadata tables and indexes if they do not exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_audit_checklist (
        chat_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        radar_sources TEXT NOT NULL,
        salience_score REAL,
        primary_category TEXT,
        start_date TEXT,
        message_count INTEGER,
        total_words INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        findings_summary TEXT,
        key_quotes TEXT,
        thematic_tags TEXT,
        notes TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, thread_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thread_checklist_status ON thread_audit_checklist(chat_id, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thread_checklist_radar ON thread_audit_checklist(chat_id, radar_sources);")
    conn.commit()


def is_thread_checklist_waived(conn: sqlite3.Connection, chat_id: str) -> Tuple[bool, Optional[str]]:
    """Check if thread audit checklist is currently flagged as waived/exempt in metadata."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"thread_checklist_mode_{chat_id}",))
        row = cur.fetchone()
        if row and row[0] == "waived":
            cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"thread_checklist_waiver_reason_{chat_id}",))
            r_row = cur.fetchone()
            reason = r_row[0] if r_row else "Ad-hoc task / partial inquiry"
            return True, reason
    except Exception:
        pass
    return False, None


def waive_thread_checklist(conn: sqlite3.Connection, chat_id: str, reason: str = "Ad-hoc task / partial inquiry") -> int:
    """Waive thread checklist by marking all pending threads as not_applicable and setting metadata flag."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("""
    UPDATE thread_audit_checklist
    SET status = 'not_applicable',
        notes = coalesce(notes || ' | ', '') || 'Waived: ' || ?,
        updated_at = ?
    WHERE chat_id = ? AND status = 'pending';
    """, (reason, now_iso, chat_id))
    waived_count = cur.rowcount
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, 'waived');", (f"thread_checklist_mode_{chat_id}",))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?);", (f"thread_checklist_waiver_reason_{chat_id}", reason))
    conn.commit()
    return waived_count


def enable_thread_checklist(conn: sqlite3.Connection, chat_id: str) -> int:
    """Re-enable thread checklist after waiver by changing not_applicable items back to pending."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("""
    UPDATE thread_audit_checklist
    SET status = 'pending',
        updated_at = ?
    WHERE chat_id = ? AND status = 'not_applicable';
    """, (now_iso, chat_id))
    re_enabled = cur.rowcount
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, 'active');", (f"thread_checklist_mode_{chat_id}",))
    cur.execute("DELETE FROM metadata WHERE key = ?;", (f"thread_checklist_waiver_reason_{chat_id}",))
    conn.commit()
    return re_enabled


def init_thread_checklist(
    conn: sqlite3.Connection,
    chat_id: str,
    reset: bool = False,
    min_salience_other: float = 2.0,
    min_words_intensive: int = 60,
    min_messages_intensive: int = 8,
    limit_intensive: int = 0
) -> Dict[str, Any]:
    """Initialize thread audit checklist for a given chat."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    if reset:
        cur.execute("DELETE FROM thread_audit_checklist WHERE chat_id = ?;", (chat_id,))
        cur.execute("DELETE FROM metadata WHERE key IN (?, ?);", 
                    (f"thread_checklist_mode_{chat_id}", f"thread_checklist_waiver_reason_{chat_id}"))
        conn.commit()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    has_triage = cur.fetchone()[0] > 0

    thread_candidates: Dict[str, Dict[str, Any]] = {}

    if has_triage:
        cur.execute("PRAGMA table_info(thread_triage);")
        tcols = {col[1] for col in cur.fetchall()}
        has_atypical = "is_atypical" in tcols
        has_peak = "emotional_peak" in tcols
        has_advice = "is_advice_seeking" in tcols

        atyp_sel = "tr.is_atypical" if has_atypical else "0"
        surp_sel = "tr.interlocutor_surprised" if has_atypical else "0"
        peak_sel = "tr.emotional_peak" if has_peak else "'none'"
        adv_sel = "tr.is_advice_seeking" if has_advice else "0"

        sql_triage = f"""
        SELECT tr.thread_id, tr.salience_score, tr.primary_category,
               {atyp_sel}, {surp_sel}, {peak_sel}, {adv_sel},
               t.start_date, t.message_count, coalesce(sum(m.word_count), 0) as total_words
        FROM thread_triage tr
        JOIN threads t ON tr.thread_id = t.thread_id
        LEFT JOIN messages m ON t.thread_id = m.thread_id
        WHERE tr.chat_id = ?
        GROUP BY tr.thread_id;
        """
        cur.execute(sql_triage, (chat_id,))
        for r in cur.fetchall():
            tid = r[0]
            score = float(r[1] or 0.0)
            cat = r[2] or "general"
            is_atyp = bool(r[3])
            is_surp = bool(r[4])
            peak = r[5] or "none"
            is_adv = bool(r[6])
            start_date = r[7][:16].replace("T", " ") if r[7] else ""
            msg_count = r[8] or 0
            word_count = r[9] or 0

            radars: List[str] = []
            if is_atyp or is_surp:
                radars.append("radar_1_anomalies")
            if peak in ("profound_sadness", "euphoric_joy", "intense_rage"):
                radars.append(f"radar_2_peak:{peak}")
            if is_adv:
                radars.append("radar_3_advice_seeking")

            if not radars and score >= min_salience_other:
                radars.append("other_salient")

            if radars:
                thread_candidates[tid] = {
                    "thread_id": tid,
                    "chat_id": chat_id,
                    "radar_sources": ",".join(radars),
                    "salience_score": score,
                    "primary_category": cat,
                    "start_date": start_date,
                    "message_count": msg_count,
                    "total_words": word_count
                }

    effective_limit_intensive = limit_intensive
    if not has_triage and limit_intensive <= 0:
        effective_limit_intensive = 50

    if effective_limit_intensive > 0:
        sql_intensive = """
        SELECT t.thread_id, t.start_date, t.message_count, sum(m.word_count) as total_words
        FROM threads t
        JOIN messages m ON t.thread_id = m.thread_id
        WHERE t.chat_id = ?
        GROUP BY t.thread_id
        HAVING t.message_count >= ? AND total_words >= ?
        ORDER BY total_words DESC
        LIMIT ?;
        """
        cur.execute(sql_intensive, (chat_id, min_messages_intensive, min_words_intensive, effective_limit_intensive))
        for r in cur.fetchall():
            tid = r[0]
            start_date = r[1][:16].replace("T", " ") if r[1] else ""
            msg_count = r[2] or 0
            word_count = r[3] or 0

            if tid in thread_candidates:
                existing_radars = thread_candidates[tid]["radar_sources"].split(",")
                if "intensive_discussion" not in existing_radars:
                    existing_radars.append("intensive_discussion")
                    thread_candidates[tid]["radar_sources"] = ",".join(existing_radars)
            else:
                thread_candidates[tid] = {
                    "thread_id": tid,
                    "chat_id": chat_id,
                    "radar_sources": "intensive_discussion",
                    "salience_score": 1.5,
                    "primary_category": "intensive_discussion",
                    "start_date": start_date,
                    "message_count": msg_count,
                    "total_words": word_count
                }

    now_iso = datetime.now(timezone.utc).isoformat()
    inserted_count = 0
    updated_sources = 0

    for tid, data in thread_candidates.items():
        cur.execute("SELECT radar_sources, status FROM thread_audit_checklist WHERE chat_id = ? AND thread_id = ?;", (chat_id, tid))
        row = cur.fetchone()
        if not row:
            cur.execute("""
            INSERT INTO thread_audit_checklist (
                chat_id, thread_id, radar_sources, salience_score, primary_category,
                start_date, message_count, total_words, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?);
            """, (
                chat_id, tid, data["radar_sources"], data["salience_score"], data["primary_category"],
                data["start_date"], data["message_count"], data["total_words"], now_iso
            ))
            inserted_count += 1
        else:
            existing_srcs = set(row[0].split(","))
            new_srcs = set(data["radar_sources"].split(","))
            combined = existing_srcs.union(new_srcs)
            if combined != existing_srcs:
                cur.execute("""
                UPDATE thread_audit_checklist
                SET radar_sources = ?, updated_at = ?
                WHERE chat_id = ? AND thread_id = ?;
                """, (",".join(sorted(combined)), now_iso, chat_id, tid))
                updated_sources += 1

    conn.commit()

    cur.execute("SELECT count(*) FROM thread_audit_checklist WHERE chat_id = ?;", (chat_id,))
    total_in_db = cur.fetchone()[0]

    return {
        "chat_id": chat_id,
        "total_threads_enrolled": total_in_db,
        "newly_inserted": inserted_count,
        "updated_sources": updated_sources
    }


def get_thread_checklist_stats(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Retrieve detailed stats and breakdown of the thread audit checklist."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()

    is_waived, waiver_reason = is_thread_checklist_waived(conn, chat_id)

    cur.execute("""
    SELECT count(*),
           sum(case when status = 'completed' then 1 else 0 end),
           sum(case when status = 'pending' then 1 else 0 end),
           sum(case when status = 'skipped' then 1 else 0 end),
           sum(case when status = 'not_applicable' then 1 else 0 end)
    FROM thread_audit_checklist
    WHERE chat_id = ?;
    """, (chat_id,))
    row = cur.fetchone()
    total = row[0] or 0
    completed = row[1] or 0
    pending = row[2] or 0
    skipped = row[3] or 0
    not_applicable = row[4] or 0

    resolved = completed + skipped + not_applicable
    progress_pct = (resolved / total * 100.0) if total > 0 else 0.0

    cur.execute("""
    SELECT radar_sources, status, count(*)
    FROM thread_audit_checklist
    WHERE chat_id = ?
    GROUP BY radar_sources, status;
    """, (chat_id,))
    radar_counts: Dict[str, Dict[str, int]] = {}
    for r in cur.fetchall():
        r_sources = r[0]
        r_status = r[1]
        r_count = r[2]
        for src in r_sources.split(","):
            prefix = src.split(":")[0]
            if prefix not in radar_counts:
                radar_counts[prefix] = {"total": 0, "completed": 0, "pending": 0, "skipped": 0}
            radar_counts[prefix]["total"] += r_count
            if r_status in radar_counts[prefix]:
                radar_counts[prefix][r_status] += r_count

    cur.execute("""
    SELECT thread_id, radar_sources, salience_score, primary_category, start_date, message_count, total_words
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'pending'
    ORDER BY salience_score DESC, total_words DESC
    LIMIT 3;
    """, (chat_id,))
    next_pending = []
    for r in cur.fetchall():
        next_pending.append({
            "thread_id": r[0],
            "radar_sources": r[1],
            "salience_score": r[2],
            "primary_category": r[3],
            "start_date": r[4],
            "message_count": r[5],
            "total_words": r[6]
        })

    return {
        "chat_id": chat_id,
        "is_waived": is_waived,
        "waiver_reason": waiver_reason,
        "total": total,
        "completed": completed,
        "pending": pending,
        "skipped": skipped,
        "not_applicable": not_applicable,
        "resolved": resolved,
        "progress_pct": progress_pct,
        "radars": radar_counts,
        "next_pending": next_pending
    }


def update_thread_item(
    conn: sqlite3.Connection,
    chat_id: str,
    thread_id: str,
    status: str,
    findings: Optional[str] = None,
    quotes: Optional[str] = None,
    tags: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """Update an individual thread audit record."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute("SELECT thread_id FROM thread_audit_checklist WHERE chat_id = ? AND thread_id = ?;", (chat_id, thread_id))
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO thread_audit_checklist (
            chat_id, thread_id, radar_sources, salience_score, primary_category,
            start_date, message_count, total_words, status, updated_at
        ) VALUES (?, ?, 'manual_enrollment', 2.0, 'general', '', 0, 0, 'pending', ?);
        """, (chat_id, thread_id, now_iso))

    updates = ["status = ?", "updated_at = ?"]
    params: List[Any] = [status, now_iso]

    if findings is not None:
        updates.append("findings_summary = ?")
        params.append(findings)
    if quotes is not None:
        updates.append("key_quotes = ?")
        params.append(quotes)
    if tags is not None:
        updates.append("thematic_tags = ?")
        params.append(tags)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    params.extend([chat_id, thread_id])
    sql = f"UPDATE thread_audit_checklist SET {', '.join(updates)} WHERE chat_id = ? AND thread_id = ?;"
    cur.execute(sql, params)
    conn.commit()
    return cur.rowcount > 0


def resolve_chat_id(conn: sqlite3.Connection, chat_input: Optional[str]) -> Optional[str]:
    """Helper to resolve chat_id from id or name."""
    cur = conn.cursor()
    cur.execute("SELECT chat_id, chat_name FROM chats;")
    rows = cur.fetchall()
    if not rows:
        return None
    if not chat_input:
        if len(rows) == 1:
            return rows[0][0]
        return None
    for cid, cname in rows:
        if cid == chat_input or (cname and cname.lower() == chat_input.lower()):
            return cid
    return None
