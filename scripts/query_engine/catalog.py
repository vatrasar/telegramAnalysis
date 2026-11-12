"""Chat resolution and indexed chats catalog operations."""

import sys
import sqlite3
from typing import List, Dict, Any, Optional, Tuple


def get_chats_catalog(db_path: str) -> List[Dict[str, Any]]:
    """Retrieve catalog of all indexed chats in the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chats';")
    if cur.fetchone()[0] == 0:
        conn.close()
        return []

    cur.execute("""
    SELECT chat_id, chat_name, chat_type, source_files, total_messages, total_threads, start_date, end_date
    FROM chats
    ORDER BY total_messages DESC;
    """)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "chat_id": r[0],
            "chat_name": r[1],
            "chat_type": r[2],
            "source_files": r[3],
            "total_messages": r[4],
            "total_threads": r[5],
            "start_date": r[6][:10] if r[6] else None,
            "end_date": r[7][:10] if r[7] else None
        }
        for r in rows
    ]


def resolve_chat(db_path: str, chat_arg: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Resolve chat_arg into (chat_id, chat_name).

    Matches by exact chat_id, exact chat_name, or case-insensitive substring.
    """
    if not chat_arg:
        return None, None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chats';")
    if cur.fetchone()[0] == 0:
        conn.close()
        return chat_arg, chat_arg

    # 1. Exact match on chat_id
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE chat_id = ?;", (chat_arg,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0], row[1]

    # 2. Case-insensitive exact match on chat_name
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE lower(chat_name) = lower(?);", (chat_arg,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0], row[1]

    # 3. Case-insensitive substring match
    cur.execute("SELECT chat_id, chat_name FROM chats WHERE lower(chat_name) LIKE lower(?);", (f"%{chat_arg}%",))
    rows = cur.fetchall()
    conn.close()

    if len(rows) == 1:
        return rows[0][0], rows[0][1]
    elif len(rows) > 1:
        print(f"[!] Ambiguous chat identifier '{chat_arg}'. Matches multiple chats:")
        for r in rows:
            print(f"    - ID: {r[0]} | Name: '{r[1]}'")
        print("    Please specify an exact chat_id using --chat <id>.")
        sys.exit(1)

    print(f"[!] Chat '{chat_arg}' not found in database.")
    print("    Available chats:")
    catalog = get_chats_catalog(db_path)
    for c in catalog:
        print(f"    - {c['chat_id']}: '{c['chat_name']}' ({c['total_messages']} msgs)")
    sys.exit(1)


def print_chats_catalog(chats: List[Dict[str, Any]]) -> None:
    """Print ASCII table of indexed chats catalog."""
    print("\n" + "=" * 80)
    print("📁 INDEXED CHATS CATALOG")
    print("=" * 80)
    if not chats:
        print("No chats found in database.")
        return

    print(f"{'Chat ID':<16} {'Chat Name':<24} {'Messages':<10} {'Threads':<10} {'Date Range':<22}")
    print("-" * 84)
    for c in chats:
        c_id = c["chat_id"][:14]
        c_name = c["chat_name"][:22]
        d_range = f"{c['start_date'] or ''} to {c['end_date'] or ''}"
        print(f"{c_id:<16} {c_name:<24} {c['total_messages']:<10,} {c['total_threads']:<10,} {d_range:<22}")
    print("=" * 80)
