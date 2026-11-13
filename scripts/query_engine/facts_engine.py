"""Discovered facts repository, sphere tagging, and thread inspection state tracking."""

import re
import json
import sqlite3
import datetime as dt_module
from typing import List, Dict, Any, Optional, Tuple, Set

VALID_SPHERES: Set[str] = {"A", "B", "C", "D", "E", "F"}

SPHERE_TO_CATEGORY: Dict[str, str] = {
    "A": "sphere_a_social",
    "B": "sphere_b_career",
    "C": "sphere_c_politics",
    "D": "sphere_d_family",
    "E": "sphere_e_romantic",
    "F": "sphere_f_leisure",
}

CATEGORY_TO_SPHERE: Dict[str, str] = {v: k for k, v in SPHERE_TO_CATEGORY.items()}

CATEGORY_ALIASES: Dict[str, Tuple[str, Optional[str]]] = {
    "social": ("sphere_a_social", "A"),
    "friends": ("sphere_a_social", "A"),
    "friendship": ("sphere_a_social", "A"),
    "a": ("sphere_a_social", "A"),
    "career": ("sphere_b_career", "B"),
    "work": ("sphere_b_career", "B"),
    "job": ("sphere_b_career", "B"),
    "finance": ("sphere_b_career", "B"),
    "finances": ("sphere_b_career", "B"),
    "b": ("sphere_b_career", "B"),
    "politics": ("sphere_c_politics", "C"),
    "political": ("sphere_c_politics", "C"),
    "worldview": ("sphere_c_politics", "C"),
    "tech": ("sphere_c_politics", "C"),
    "technology": ("sphere_c_politics", "C"),
    "c": ("sphere_c_politics", "C"),
    "family": ("sphere_d_family", "D"),
    "parents": ("sphere_d_family", "D"),
    "roots": ("sphere_d_family", "D"),
    "childhood": ("sphere_d_family", "D"),
    "d": ("sphere_d_family", "D"),
    "romantic": ("sphere_e_romantic", "E"),
    "romance": ("sphere_e_romantic", "E"),
    "attachment": ("sphere_e_romantic", "E"),
    "partner": ("sphere_e_romantic", "E"),
    "e": ("sphere_e_romantic", "E"),
    "leisure": ("sphere_f_leisure", "F"),
    "sports": ("sphere_f_leisure", "F"),
    "travel": ("sphere_f_leisure", "F"),
    "animals": ("sphere_f_leisure", "F"),
    "hobbies": ("sphere_f_leisure", "F"),
    "f": ("sphere_f_leisure", "F"),
    "biography": ("biography_timeline", None),
    "timeline": ("biography_timeline", None),
    "history": ("biography_timeline", None),
    "psychodynamics": ("psychodynamics", None),
    "defense": ("psychodynamics", None),
    "trauma": ("psychodynamics", None),
    "crisis": ("psychodynamics", None),
    "ocean": ("personality_ocean", None),
    "bigfive": ("personality_ocean", None),
    "traits": ("personality_ocean", None),
    "playbook": ("operational_playbook", None),
    "advice": ("operational_playbook", None),
    "rules": ("operational_playbook", None),
}

DEFAULT_TARGET_AGENTS: Dict[str, str] = {
    "sphere_a_social": "life-sphere-investigator",
    "sphere_b_career": "life-sphere-investigator",
    "sphere_c_politics": "life-sphere-investigator",
    "sphere_d_family": "life-sphere-investigator",
    "sphere_e_romantic": "life-sphere-investigator",
    "sphere_f_leisure": "life-sphere-investigator",
    "biography_timeline": "chapter-drafter",
    "psychodynamics": "forensic-thread-investigator",
    "personality_ocean": "chapter-drafter",
    "operational_playbook": "operational-playbook-architect",
}


def normalize_category_and_sphere(raw_category: Optional[str], raw_sphere: Optional[str]) -> Tuple[str, Optional[str]]:
    """Normalize raw category and sphere string to canonical pairs."""
    cat = (raw_category or "").strip().lower()
    sph = (raw_sphere or "").strip().upper() if raw_sphere else None

    if sph in VALID_SPHERES and not cat:
        return SPHERE_TO_CATEGORY[sph], sph

    if cat in CATEGORY_ALIASES:
        c, s = CATEGORY_ALIASES[cat]
        return c, sph or s

    if cat in SPHERE_TO_CATEGORY.values():
        return cat, sph or CATEGORY_TO_SPHERE.get(cat)

    if sph in VALID_SPHERES:
        return cat or SPHERE_TO_CATEGORY[sph], sph

    return cat or "general_finding", sph


def extract_anchor_id_from_quote(quote: str) -> Optional[int]:
    """Attempt to extract anchor message ID from quote [#12345 | ...]."""
    m = re.search(r"\[#(\d+)", quote)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def ensure_facts_tables(conn: sqlite3.Connection) -> None:
    """Ensure inspected_threads and discovered_facts tables and indexes exist."""
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
        PRIMARY KEY (chat_id, thread_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inspected_threads_chat ON inspected_threads(chat_id);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS discovered_facts (
        fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        thread_id TEXT,
        anchor_msg_id INTEGER,
        category TEXT NOT NULL,
        sphere_id TEXT,
        target_agent TEXT,
        fact_summary TEXT NOT NULL,
        verbatim_quote TEXT NOT NULL,
        discovered_by TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_chat ON discovered_facts(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_cat ON discovered_facts(chat_id, category);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_sphere ON discovered_facts(chat_id, sphere_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_thread ON discovered_facts(chat_id, thread_id);")
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
) -> Dict[str, Any]:
    """Mark a thread as inspected/read so subsequent stages do not re-read it blindly."""
    ensure_facts_tables(conn)
    cur = conn.cursor()
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    cur.execute("""
    INSERT INTO inspected_threads (chat_id, thread_id, inspected_by, stage, findings_summary, thematic_tags, covered_spheres, inspected_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, thread_id) DO UPDATE SET
        inspected_by = excluded.inspected_by,
        stage = excluded.stage,
        findings_summary = coalesce(inspected_threads.findings_summary || ' | ', '') || excluded.findings_summary,
        thematic_tags = coalesce(inspected_threads.thematic_tags || ',', '') || excluded.thematic_tags,
        covered_spheres = coalesce(inspected_threads.covered_spheres || ',', '') || excluded.covered_spheres,
        inspected_at = excluded.inspected_at;
    """, (chat_id, thread_id, inspected_by, stage, findings, tags, spheres, now_iso))

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
    ensure_facts_tables(conn)
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
    ensure_facts_tables(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT inspected_by, stage, findings_summary, thematic_tags, covered_spheres, inspected_at
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
        }
    return False, None


def record_discovered_fact(
    conn: sqlite3.Connection,
    chat_id: str,
    fact_summary: str,
    verbatim_quote: str,
    category: Optional[str] = None,
    sphere_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    anchor_msg_id: Optional[int] = None,
    target_agent: Optional[str] = None,
    discovered_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Record an anchored discovered fact tagged for downstream report agents."""
    ensure_facts_tables(conn)
    cur = conn.cursor()
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    canon_cat, canon_sph = normalize_category_and_sphere(category, sphere_id)
    anchor_id = anchor_msg_id or extract_anchor_id_from_quote(verbatim_quote)
    agent = target_agent or DEFAULT_TARGET_AGENTS.get(canon_cat, "life-sphere-investigator")

    cur.execute("""
    INSERT INTO discovered_facts (
        chat_id, thread_id, anchor_msg_id, category, sphere_id,
        target_agent, fact_summary, verbatim_quote, discovered_by, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        chat_id, thread_id, anchor_id, canon_cat, canon_sph,
        agent, fact_summary.strip(), verbatim_quote.strip(),
        discovered_by or "agent", now_iso
    ))
    fact_id = cur.lastrowid
    conn.commit()

    return {
        "status": "success",
        "fact_id": fact_id,
        "chat_id": chat_id,
        "thread_id": thread_id,
        "anchor_msg_id": anchor_id,
        "category": canon_cat,
        "sphere_id": canon_sph,
        "target_agent": agent,
        "fact_summary": fact_summary.strip(),
        "created_at": now_iso,
    }


def record_facts_batch(
    conn: sqlite3.Connection,
    chat_id: str,
    facts: List[Dict[str, Any]],
    discovered_by: Optional[str] = None,
    default_thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Batch record multiple discovered facts in a single transaction."""
    ensure_facts_tables(conn)
    recorded = []
    for item in facts:
        summary = item.get("summary") or item.get("fact_summary") or item.get("fact") or ""
        quote = item.get("quote") or item.get("verbatim_quote") or ""
        cat = item.get("category") or item.get("suggested_category")
        sph = item.get("sphere") or item.get("sphere_id")
        tid = item.get("thread_id") or default_thread_id
        anchor = item.get("anchor_msg_id")
        agent = item.get("target_agent")
        discov = item.get("discovered_by") or discovered_by

        if not summary or not quote:
            continue

        res = record_discovered_fact(
            conn=conn,
            chat_id=chat_id,
            fact_summary=summary,
            verbatim_quote=quote,
            category=cat,
            sphere_id=sph,
            thread_id=tid,
            anchor_msg_id=anchor,
            target_agent=agent,
            discovered_by=discov,
        )
        recorded.append(res)

    return {
        "status": "success",
        "chat_id": chat_id,
        "recorded_count": len(recorded),
        "facts": recorded,
    }


def get_discovered_facts(
    conn: sqlite3.Connection,
    chat_id: str,
    category: Optional[str] = None,
    sphere_id: Optional[str] = None,
    target_agent: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve filtered discovered facts for a chat."""
    ensure_facts_tables(conn)
    cur = conn.cursor()
    sql = """
    SELECT fact_id, chat_id, thread_id, anchor_msg_id, category, sphere_id,
           target_agent, fact_summary, verbatim_quote, discovered_by, created_at
    FROM discovered_facts
    WHERE chat_id = ?
    """
    params: List[Any] = [chat_id]

    if sphere_id:
        sql += " AND sphere_id = ?"
        params.append(sphere_id.upper())
    elif category:
        canon_cat, canon_sph = normalize_category_and_sphere(category, None)
        sql += " AND (category = ? OR category LIKE ?)"
        params.extend([canon_cat, f"%{category}%"])

    if target_agent:
        sql += " AND target_agent = ?"
        params.append(target_agent)

    if thread_id:
        sql += " AND thread_id = ?"
        params.append(thread_id)

    sql += " ORDER BY fact_id ASC;"
    cur.execute(sql, params)
    rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "fact_id": r[0],
            "chat_id": r[1],
            "thread_id": r[2],
            "anchor_msg_id": r[3],
            "category": r[4],
            "sphere_id": r[5],
            "target_agent": r[6],
            "fact_summary": r[7],
            "verbatim_quote": r[8],
            "discovered_by": r[9],
            "created_at": r[10],
        })
    return results


def print_discovered_facts(facts: List[Dict[str, Any]], filter_label: Optional[str] = None) -> None:
    """Pretty print discovered facts in terminal format."""
    print("\n" + "=" * 80)
    title = f"📋 DISCOVERED FACTS & PRE-EXTRACTED EVIDENCE"
    if filter_label:
        title += f" [{filter_label}]"
    print(title)
    print("=" * 80)

    if not facts:
        print("  (No facts recorded yet for this criteria)")
        print("=" * 80 + "\n")
        return

    for f in facts:
        sph_str = f"Sphere {f['sphere_id']} | " if f.get("sphere_id") else ""
        tid_str = f"Thread: {f['thread_id']} | " if f.get("thread_id") else ""
        print(f"\n[Fact #{f['fact_id']}] {sph_str}Category: {f['category']} | Target: {f['target_agent']}")
        print(f"  {tid_str}Discovered by: {f['discovered_by']} ({f['created_at'][:10]})")
        print(f"  Summary: {f['fact_summary']}")
        print(f"  Quote:   > {f['verbatim_quote']}")
    print("\n" + "=" * 80 + "\n")


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
