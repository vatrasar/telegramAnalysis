"""Discovered facts repository, 1:N quote evidence relations, and sphere tagging."""

import re
import json
import sqlite3
import datetime as dt_module
from typing import List, Dict, Any, Optional, Tuple, Set, Union

# Re-export thread inspection functions for backward compatibility
from .inspected_threads import (
    ensure_inspected_threads_table,
    mark_thread_inspected,
    get_inspected_threads,
    is_thread_inspected,
    print_inspected_threads,
)

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
    "social": ("sphere_a_social", "A"), "friends": ("sphere_a_social", "A"), "friendship": ("sphere_a_social", "A"), "a": ("sphere_a_social", "A"),
    "career": ("sphere_b_career", "B"), "work": ("sphere_b_career", "B"), "job": ("sphere_b_career", "B"), "finance": ("sphere_b_career", "B"), "finances": ("sphere_b_career", "B"), "b": ("sphere_b_career", "B"),
    "politics": ("sphere_c_politics", "C"), "political": ("sphere_c_politics", "C"), "worldview": ("sphere_c_politics", "C"), "tech": ("sphere_c_politics", "C"), "technology": ("sphere_c_politics", "C"), "c": ("sphere_c_politics", "C"),
    "family": ("sphere_d_family", "D"), "parents": ("sphere_d_family", "D"), "roots": ("sphere_d_family", "D"), "childhood": ("sphere_d_family", "D"), "d": ("sphere_d_family", "D"),
    "romantic": ("sphere_e_romantic", "E"), "romance": ("sphere_e_romantic", "E"), "attachment": ("sphere_e_romantic", "E"), "partner": ("sphere_e_romantic", "E"), "e": ("sphere_e_romantic", "E"),
    "leisure": ("sphere_f_leisure", "F"), "sports": ("sphere_f_leisure", "F"), "travel": ("sphere_f_leisure", "F"), "animals": ("sphere_f_leisure", "F"), "hobbies": ("sphere_f_leisure", "F"), "f": ("sphere_f_leisure", "F"),
    "biography": ("biography_timeline", None), "timeline": ("biography_timeline", None), "history": ("biography_timeline", None),
    "psychodynamics": ("psychodynamics", None), "defense": ("psychodynamics", None), "trauma": ("psychodynamics", None), "crisis": ("psychodynamics", None),
    "ocean": ("personality_ocean", None), "bigfive": ("personality_ocean", None), "traits": ("personality_ocean", None),
    "playbook": ("operational_playbook", None), "advice": ("operational_playbook", None), "rules": ("operational_playbook", None),
}

DEFAULT_TARGET_AGENTS: Dict[str, str] = {
    "sphere_a_social": "life-sphere-investigator", "sphere_b_career": "life-sphere-investigator",
    "sphere_c_politics": "life-sphere-investigator", "sphere_d_family": "life-sphere-investigator",
    "sphere_e_romantic": "life-sphere-investigator", "sphere_f_leisure": "life-sphere-investigator",
    "biography_timeline": "chapter-drafter", "psychodynamics": "forensic-thread-investigator",
    "personality_ocean": "chapter-drafter", "operational_playbook": "chapter-drafter",
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
    """Ensure inspected_threads, discovered_facts, and fact_quotes tables and indexes exist."""
    ensure_inspected_threads_table(conn)
    cur = conn.cursor()

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
    cur.execute("PRAGMA table_info(discovered_facts);")
    f_cols = {c[1] for c in cur.fetchall()}
    if "subject" not in f_cols:
        cur.execute("ALTER TABLE discovered_facts ADD COLUMN subject TEXT DEFAULT '';")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_chat ON discovered_facts(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_cat ON discovered_facts(chat_id, category);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_sphere ON discovered_facts(chat_id, sphere_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_thread ON discovered_facts(chat_id, thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_discovered_facts_subj ON discovered_facts(chat_id, subject);")

    # Table 2: 1:N Relation for Fact Quotes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fact_quotes (
        quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_id INTEGER NOT NULL REFERENCES discovered_facts(fact_id) ON DELETE CASCADE,
        chat_id TEXT NOT NULL,
        thread_id TEXT,
        msg_id INTEGER NOT NULL,
        sender TEXT,
        timestamp TEXT,
        verbatim_quote TEXT NOT NULL,
        evidence_role TEXT DEFAULT 'core_evidence',
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fact_quotes_fact_id ON fact_quotes(fact_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fact_quotes_msg_id ON fact_quotes(chat_id, msg_id);")

    # One-time automated backward migration of single quotes into fact_quotes
    cur.execute("""
    INSERT INTO fact_quotes (fact_id, chat_id, thread_id, msg_id, verbatim_quote, created_at, evidence_role)
    SELECT f.fact_id, f.chat_id, f.thread_id, f.anchor_msg_id, f.verbatim_quote, f.created_at, 'core_evidence'
    FROM discovered_facts f
    WHERE f.anchor_msg_id IS NOT NULL AND length(trim(f.verbatim_quote)) > 0
      AND NOT EXISTS (
          SELECT 1 FROM fact_quotes fq WHERE fq.fact_id = f.fact_id AND fq.msg_id = f.anchor_msg_id
      );
    """)
    conn.commit()


def normalize_quote_entries(
    raw_quotes: Union[None, str, List[Union[str, Dict[str, Any]]]],
    fallback_quote: Optional[str] = None,
    default_anchor: Optional[int] = None,
    default_role: str = "core_evidence"
) -> List[Dict[str, Any]]:
    """Parse, extract anchor IDs, and normalize quotes into structured dictionaries."""
    normalized: List[Dict[str, Any]] = []

    items: List[Any] = []
    if isinstance(raw_quotes, list):
        items.extend(raw_quotes)
    elif isinstance(raw_quotes, str) and raw_quotes.strip():
        items.append(raw_quotes.strip())

    if fallback_quote and fallback_quote.strip() and not items:
        items.append(fallback_quote.strip())

    for item in items:
        if isinstance(item, dict):
            q_text = item.get("quote") or item.get("verbatim_quote") or ""
            m_id = item.get("msg_id") or item.get("anchor_msg_id") or extract_anchor_id_from_quote(q_text) or default_anchor
            role = item.get("role") or item.get("evidence_role") or default_role
            sender = item.get("sender") or ""
            ts = item.get("timestamp") or item.get("date") or ""
            if q_text:
                normalized.append({
                    "msg_id": int(m_id) if m_id else 0,
                    "verbatim_quote": q_text.strip(),
                    "evidence_role": role,
                    "sender": sender,
                    "timestamp": ts,
                })
        elif isinstance(item, str) and item.strip():
            m_id = extract_anchor_id_from_quote(item) or default_anchor
            normalized.append({
                "msg_id": int(m_id) if m_id else 0,
                "verbatim_quote": item.strip(),
                "evidence_role": default_role,
                "sender": "",
                "timestamp": "",
            })
    return normalized


def record_discovered_fact(
    conn: sqlite3.Connection,
    chat_id: str,
    fact_summary: str,
    verbatim_quote: Optional[str] = None,
    quotes: Optional[List[Union[str, Dict[str, Any]]]] = None,
    category: Optional[str] = None,
    sphere_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    anchor_msg_id: Optional[int] = None,
    target_agent: Optional[str] = None,
    discovered_by: Optional[str] = None,
    subject: str = "",
    fact_id: Optional[int] = None,
    corroborate_with_system1: bool = True,
    default_role: str = "core_evidence"
) -> Dict[str, Any]:
    """
    Record an anchored discovered fact with 1:N quotes.
    
    If corroborate_with_system1 is True (and fact_id is None), calls System-1 Decider
    to check whether this proposal matches an existing domain fact, attaching quotes
    to that existing fact instead of creating an unwanted duplicate.
    """
    ensure_facts_tables(conn)
    cur = conn.cursor()
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    canon_cat, canon_sph = normalize_category_and_sphere(category, sphere_id)
    agent = target_agent or DEFAULT_TARGET_AGENTS.get(canon_cat, "life-sphere-investigator")
    subj_val = (subject or "").strip()
    norm_quotes = normalize_quote_entries(quotes, fallback_quote=verbatim_quote, default_anchor=anchor_msg_id, default_role=default_role)

    # 1. Explicit target fact_id requested
    target_fact_id = fact_id

    # 2. Automated System-1 Corroboration / Deduplication Check
    if not target_fact_id and corroborate_with_system1:
        from .fact_corroboration_decider import match_or_deduplicate_fact
        verdict, matched_id, rationale = match_or_deduplicate_fact(
            conn=conn,
            chat_id=chat_id,
            candidate_summary=fact_summary,
            category=canon_cat,
            sphere_id=canon_sph,
            candidate_quotes=norm_quotes,
            subject=subj_val,
        )
        if verdict == "corroborates_existing" and matched_id:
            target_fact_id = matched_id

    # CASE A: Corroborate existing fact (Attach quotes)
    if target_fact_id:
        cur.execute("SELECT fact_id, fact_summary FROM discovered_facts WHERE fact_id = ? AND chat_id = ?;", (target_fact_id, chat_id))
        row = cur.fetchone()
        if row:
            added_quotes = 0
            for q in norm_quotes:
                # Check for existing quote by msg_id
                cur.execute("SELECT count(*) FROM fact_quotes WHERE fact_id = ? AND msg_id = ?;", (target_fact_id, q["msg_id"]))
                if cur.fetchone()[0] == 0:
                    cur.execute("""
                    INSERT INTO fact_quotes (fact_id, chat_id, thread_id, msg_id, sender, timestamp, verbatim_quote, evidence_role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (target_fact_id, chat_id, thread_id, q["msg_id"], q.get("sender", ""), q.get("timestamp", ""), q["verbatim_quote"], q.get("evidence_role", "core_evidence"), now_iso))
                    added_quotes += 1
            conn.commit()
            return {
                "status": "corroborated",
                "action": "quotes_attached",
                "fact_id": target_fact_id,
                "fact_summary": row[1],
                "quotes_added": added_quotes,
                "total_quotes_input": len(norm_quotes)
            }

    # CASE B: Create new fact + attach quotes
    primary_anchor = norm_quotes[0]["msg_id"] if norm_quotes and norm_quotes[0]["msg_id"] > 0 else anchor_msg_id
    primary_quote = norm_quotes[0]["verbatim_quote"] if norm_quotes else (verbatim_quote or "")

    cur.execute("""
    INSERT INTO discovered_facts (
        chat_id, thread_id, anchor_msg_id, category, sphere_id,
        target_agent, fact_summary, verbatim_quote, discovered_by, created_at, subject
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        chat_id, thread_id, primary_anchor, canon_cat, canon_sph,
        agent, fact_summary.strip(), primary_quote.strip(),
        discovered_by or "agent", now_iso, subj_val
    ))
    new_fact_id = cur.lastrowid

    for q in norm_quotes:
        cur.execute("""
        INSERT INTO fact_quotes (fact_id, chat_id, thread_id, msg_id, sender, timestamp, verbatim_quote, evidence_role, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (new_fact_id, chat_id, thread_id, q["msg_id"], q.get("sender", ""), q.get("timestamp", ""), q["verbatim_quote"], q.get("evidence_role", "core_evidence"), now_iso))

    conn.commit()
    return {
        "status": "success",
        "action": "created",
        "fact_id": new_fact_id,
        "chat_id": chat_id,
        "subject": subj_val,
        "thread_id": thread_id,
        "anchor_msg_id": primary_anchor,
        "category": canon_cat,
        "sphere_id": canon_sph,
        "target_agent": agent,
        "fact_summary": fact_summary.strip(),
        "quotes_count": len(norm_quotes),
        "created_at": now_iso,
    }


def record_facts_batch(
    conn: sqlite3.Connection,
    chat_id: str,
    facts: List[Dict[str, Any]],
    discovered_by: Optional[str] = None,
    default_thread_id: Optional[str] = None,
    default_subject: Optional[str] = None,
    corroborate_with_system1: bool = True,
) -> Dict[str, Any]:
    """Batch record multiple discovered facts with 1:N quote support."""
    ensure_facts_tables(conn)
    recorded = []
    for item in facts:
        summary = item.get("summary") or item.get("fact_summary") or item.get("fact") or ""
        q_list = item.get("quotes") or item.get("evidence")
        single_quote = item.get("quote") or item.get("verbatim_quote")
        cat = item.get("category") or item.get("suggested_category")
        sph = item.get("sphere") or item.get("sphere_id")
        tid = item.get("thread_id") or default_thread_id
        anchor = item.get("anchor_msg_id")
        agent = item.get("target_agent")
        discov = item.get("discovered_by") or discovered_by
        subj = item.get("subject") or default_subject or ""
        f_id = item.get("fact_id")

        if not summary or (not q_list and not single_quote):
            continue

        res = record_discovered_fact(
            conn=conn,
            chat_id=chat_id,
            fact_summary=summary,
            verbatim_quote=single_quote,
            quotes=q_list,
            category=cat,
            sphere_id=sph,
            thread_id=tid,
            anchor_msg_id=anchor,
            target_agent=agent,
            discovered_by=discov,
            subject=subj,
            fact_id=f_id,
            corroborate_with_system1=corroborate_with_system1
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
    subject: Optional[str] = None,
    include_quotes: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieve filtered discovered facts with their linked 1:N quotes."""
    ensure_facts_tables(conn)
    cur = conn.cursor()
    sql = """
    SELECT fact_id, chat_id, thread_id, anchor_msg_id, category, sphere_id,
           target_agent, fact_summary, verbatim_quote, discovered_by, created_at, subject
    FROM discovered_facts
    WHERE 1=1
    """
    params: List[Any] = []
    if chat_id:
        sql += " AND chat_id = ?"
        params.append(chat_id)

    if subject and str(subject).strip():
        sql += " AND (lower(coalesce(subject, '')) = lower(?) OR subject = '' OR subject IS NULL)"
        params.append(str(subject).strip())

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
        fid = r[0]
        linked_quotes = []
        if include_quotes:
            cur.execute("""
            SELECT quote_id, msg_id, verbatim_quote, evidence_role, sender, timestamp
            FROM fact_quotes
            WHERE fact_id = ?
            ORDER BY quote_id ASC;
            """, (fid,))
            for qr in cur.fetchall():
                linked_quotes.append({
                    "quote_id": qr[0],
                    "msg_id": qr[1],
                    "verbatim_quote": qr[2],
                    "evidence_role": qr[3],
                    "sender": qr[4],
                    "timestamp": qr[5],
                })

        results.append({
            "fact_id": fid,
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
            "subject": r[11] or "",
            "quotes": linked_quotes,
        })
    return results


def export_chapter_evidence_package(
    conn: sqlite3.Connection,
    chat_id: str,
    target_chapter: Optional[str] = None,
    sphere_id: Optional[str] = None
) -> Dict[str, Any]:
    """Export complete evidence package with facts and linked quotes ready for Chapter Drafters."""
    facts = get_discovered_facts(conn, chat_id, sphere_id=sphere_id, include_quotes=True)
    return {
        "chat_id": chat_id,
        "target_chapter": target_chapter or "all",
        "total_facts": len(facts),
        "facts": facts
    }


def print_discovered_facts(facts: List[Dict[str, Any]], filter_label: Optional[str] = None) -> None:
    """Pretty print discovered facts and their linked quotes in terminal format."""
    print("\n" + "=" * 80)
    title = f"📋 DISCOVERED FACTS & LINKED EVIDENCE"
    if filter_label:
        title += f" [{filter_label}]"
    print(title)
    print("=" * 80)

    if not facts:
        print("  (No facts recorded yet for this criteria)")
        print("=" * 80 + "\n")
        return

    for f in facts:
        subj_str = f"Subject: {f['subject']} | " if f.get("subject") else ""
        sph_str = f"Sphere {f['sphere_id']} | " if f.get("sphere_id") else ""
        tid_str = f"Thread: {f['thread_id']} | " if f.get("thread_id") else ""
        quotes_count = len(f.get("quotes", []))
        print(f"\n[Fact #{f['fact_id']}] {subj_str}{sph_str}Category: {f['category']} | Quotes: {quotes_count}")
        print(f"  {tid_str}Discovered by: {f['discovered_by']} ({f['created_at'][:10]})")
        print(f"  Summary: {f['fact_summary']}")
        for q in f.get("quotes", []):
            role_tag = f"[{q['evidence_role']}] " if q.get("evidence_role") else ""
            print(f"    ↳ {role_tag}[#{q['msg_id']}] {q['verbatim_quote'][:120]}")
    print("\n" + "=" * 80 + "\n")
