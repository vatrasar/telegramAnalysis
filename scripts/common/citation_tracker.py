"""Report Citations & Evidence Reuse Tracking.

Tracks which anchor quotes have been cited across chapter and subsection files.
Provides citation awareness to prevent unnecessary duplicate quoting while strictly
prohibiting drafters from re-querying raw chat logs to hunt for replacements.
"""

import re
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Tuple


def ensure_citations_table(conn: sqlite3.Connection) -> None:
    """Ensure the report_citations table and indexes exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS report_citations (
        citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        anchor_msg_id INTEGER NOT NULL,
        chapter TEXT NOT NULL,
        section_file TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_citations_msg ON report_citations(chat_id, anchor_msg_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_citations_chat_chap ON report_citations(chat_id, chapter);")
    conn.commit()


def record_citation(
    conn: sqlite3.Connection,
    chat_id: str,
    anchor_msg_id: int,
    chapter: str,
    section_file: str = ""
) -> bool:
    """Record a citation in SQLite if not already recorded for that chapter/section."""
    ensure_citations_table(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT count(*) FROM report_citations
    WHERE chat_id = ? AND anchor_msg_id = ? AND chapter = ? AND section_file = ?;
    """, (chat_id, anchor_msg_id, chapter, section_file))
    if cur.fetchone()[0] > 0:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute("""
    INSERT INTO report_citations (chat_id, anchor_msg_id, chapter, section_file, created_at)
    VALUES (?, ?, ?, ?, ?);
    """, (chat_id, anchor_msg_id, chapter, section_file, now_iso))
    conn.commit()
    return True


def extract_anchor_ids_from_text(content: str) -> List[int]:
    """Extract message IDs from quote anchors [#<msg_id> | ...] or [#<msg_id>]."""
    matches = re.findall(r"\[#(\d+)(?:\s*\|\s*[^\]]+)?\]", content)
    return [int(m) for m in matches]


def record_citations_from_text(
    conn: sqlite3.Connection,
    chat_id: str,
    content: str,
    chapter: str,
    section_file: str = ""
) -> List[int]:
    """Extract and persist all quote anchors from a section's markdown content."""
    msg_ids = extract_anchor_ids_from_text(content)
    for mid in set(msg_ids):
        record_citation(conn, chat_id, mid, chapter, section_file)
    return msg_ids


def get_cited_quotes_map(
    conn: sqlite3.Connection,
    chat_id: str
) -> Dict[int, List[Dict[str, str]]]:
    """Retrieve map of anchor_msg_id -> list of citation locations."""
    ensure_citations_table(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT anchor_msg_id, chapter, coalesce(section_file, '')
    FROM report_citations
    WHERE chat_id = ?
    ORDER BY citation_id ASC;
    """, (chat_id,))
    
    citations_map: Dict[int, List[Dict[str, str]]] = {}
    for mid, chap, sec in cur.fetchall():
        if mid not in citations_map:
            citations_map[mid] = []
        citations_map[mid].append({"chapter": chap, "section_file": sec})
    return citations_map


def format_citation_guidance(
    is_cited: bool,
    locations: Optional[List[Dict[str, str]]] = None
) -> str:
    """Format clear, prescriptive guidance on whether and how to reuse a quote."""
    if not is_cited or not locations:
        return "UNCITED (Primary choice: fully available for this section)"
    
    loc_strs = [
        f"{loc.get('chapter', 'Report')}" + (f" ({loc['section_file']})" if loc.get("section_file") else "")
        for loc in locations
    ]
    loc_summary = ", ".join(loc_strs)
    return (
        f"CITED in: {loc_summary} | GUIDANCE: If another relevant fact exists in discovered_facts "
        f"for this subtopic, prefer the uncited one. If this is the only strong factual illustration "
        f"in the database, USE IT DIRECTLY. Strictly forbidden from searching raw chat logs for replacements."
    )
