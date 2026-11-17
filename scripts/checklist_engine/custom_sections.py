"""Custom report sections and subsections management for Evidence Curation."""

import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


def ensure_custom_sections_table(conn: sqlite3.Connection) -> None:
    """Ensure custom_report_sections table exists in SQLite database."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS custom_report_sections (
        section_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        section_title TEXT NOT NULL,
        section_type TEXT NOT NULL DEFAULT 'chapter',
        target_filename TEXT NOT NULL,
        rationale TEXT NOT NULL,
        suggested_target_agent TEXT NOT NULL DEFAULT 'chapter-drafter',
        associated_threads TEXT,
        key_quotes TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_custom_sec_chat ON custom_report_sections(chat_id);")
    conn.commit()


def propose_custom_section(
    conn: sqlite3.Connection,
    chat_id: str,
    title: str,
    rationale: str,
    target_filename: str,
    section_type: str = "chapter",
    suggested_target_agent: str = "chapter-drafter",
    associated_threads: str = "",
    key_quotes: str = ""
) -> Dict[str, Any]:
    """Record a proposal for a novel custom chapter or subsection."""
    ensure_custom_sections_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    clean_filename = target_filename.strip()
    if not clean_filename.endswith(".md"):
        clean_filename += ".md"

    cur.execute("""
    INSERT INTO custom_report_sections (
        chat_id, section_title, section_type, target_filename,
        rationale, suggested_target_agent, associated_threads,
        key_quotes, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?);
    """, (
        chat_id, title.strip(), section_type.strip(), clean_filename,
        rationale.strip(), suggested_target_agent.strip(),
        associated_threads.strip(), key_quotes.strip(), now_iso
    ))
    sec_id = cur.lastrowid
    conn.commit()

    return {
        "section_id": sec_id,
        "chat_id": chat_id,
        "section_title": title.strip(),
        "section_type": section_type.strip(),
        "target_filename": clean_filename,
        "rationale": rationale.strip(),
        "suggested_target_agent": suggested_target_agent.strip(),
        "associated_threads": associated_threads.strip(),
        "created_at": now_iso
    }


def get_custom_sections(
    conn: sqlite3.Connection,
    chat_id: str
) -> List[Dict[str, Any]]:
    """Retrieve all proposed custom sections for a given chat."""
    ensure_custom_sections_table(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT section_id, section_title, section_type, target_filename,
           rationale, suggested_target_agent, associated_threads,
           key_quotes, status, created_at
    FROM custom_report_sections
    WHERE chat_id = ?
    ORDER BY section_id ASC;
    """, (chat_id,))
    rows = cur.fetchall()

    sections = []
    for r in rows:
        sections.append({
            "section_id": r[0],
            "title": r[1],
            "type": r[2],
            "filename": r[3],
            "rationale": r[4],
            "target_agent": r[5],
            "threads": r[6] or "",
            "quotes": r[7] or "",
            "status": r[8],
            "created_at": r[9]
        })
    return sections


def print_custom_sections(conn: sqlite3.Connection, chat_id: str) -> None:
    """Print clean terminal view of proposed custom sections."""
    sections = get_custom_sections(conn, chat_id)
    print("=" * 80)
    print(f"📑 PROPOSED CUSTOM REPORT SECTIONS [Chat: {chat_id}] ({len(sections)} TOTAL)")
    print("=" * 80)
    if not sections:
        print("  No custom report sections proposed. Standard 8-chapter blueprint applies.")
        print("=" * 80)
        return

    for s in sections:
        print(f"[{s['section_id']:02d}] {s['type'].upper()}: \"{s['title']}\"")
        print(f"     Target File:  reports/<subject>_sections/{s['filename']}")
        print(f"     Drafter:      {s['target_agent']}")
        print(f"     Rationale:    {s['rationale']}")
        if s['threads']:
            print(f"     Threads:      {s['threads']}")
        if s['quotes']:
            print(f"     Anchor Quotes: {s['quotes']}")
        print("-" * 80)
    print("=" * 80)
