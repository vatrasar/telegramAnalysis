"""Entity disambiguation, descriptor registry, and lazy cardinality audits."""

import re
import sqlite3
import datetime as dt_module
from typing import List, Dict, Any, Optional


def ensure_entities_tables(conn: sqlite3.Connection) -> None:
    """Ensure chat_entities and chat_descriptors tables exist in the database."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_entities (
        entity_id TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        name_or_alias TEXT NOT NULL,
        verified_role TEXT,
        associated_descriptors TEXT,
        is_ex_partner INTEGER DEFAULT 0,
        is_romantic INTEGER DEFAULT 0,
        confidence TEXT DEFAULT 'unverified',
        first_msg_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, entity_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_chat ON chat_entities(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON chat_entities(chat_id, name_or_alias);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_descriptors (
        chat_id TEXT NOT NULL,
        descriptor TEXT NOT NULL,
        cardinality TEXT NOT NULL,
        estimated_count INTEGER DEFAULT 1,
        mapped_entity_ids TEXT,
        evidence_msg_ids TEXT,
        needs_recheck INTEGER DEFAULT 0,
        audited_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, descriptor)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_desc_chat ON chat_descriptors(chat_id);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_entity_audit (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        status TEXT NOT NULL,
        last_known_count INTEGER DEFAULT 0,
        probability REAL,
        notes TEXT,
        audited_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thread_entity_audit_chat ON thread_entity_audit(chat_id);")
    conn.commit()


def get_chat_entities(db_path: str, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve registered third-party entities scoped to chat."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    sql = """
    SELECT e.entity_id, e.chat_id, coalesce(c.chat_name, e.chat_id), e.name_or_alias,
           e.verified_role, e.associated_descriptors, e.is_ex_partner, e.is_romantic,
           e.confidence, e.first_msg_id, e.notes, e.created_at, e.updated_at
    FROM chat_entities e
    LEFT JOIN chats c ON e.chat_id = c.chat_id
    """
    params = []
    if chat_id:
        sql += " WHERE e.chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY e.name_or_alias ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "entity_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "name_or_alias": r[3],
            "verified_role": r[4] or "",
            "associated_descriptors": r[5] or "",
            "is_ex_partner": bool(r[6]),
            "is_romantic": bool(r[7]),
            "confidence": r[8] or "verified",
            "first_msg_id": r[9],
            "notes": r[10] or "",
            "created_at": r[11],
            "updated_at": r[12]
        }
        for r in rows
    ]


def print_chat_entities(entities: List[Dict[str, Any]], chat_name: Optional[str] = None) -> None:
    """Print ASCII table of registered third-party entities."""
    print("\n" + "=" * 80)
    c_label = f" [Chat: {chat_name}]" if chat_name else ""
    print(f"👥 REGISTERED THIRD-PARTY ENTITIES (CHARACTERS & SUITORS){c_label}")
    print("=" * 80)
    if not entities:
        print("No third-party entities currently registered for this chat.")
        print("Use --register-entity '<name>' --role '<role>' --desc '<descriptors>' to register.")
        print("=" * 80)
        return

    print(f"{'Name / Alias':<18} {'Role':<22} {'Ex?':<5} {'Rom?':<5} {'Descriptors / Notes':<28}")
    print("-" * 80)
    for e in entities:
        ex_str = "YES" if e["is_ex_partner"] else "no"
        rom_str = "YES" if e["is_romantic"] else "no"
        role_str = e["verified_role"][:20]
        desc_notes = e["associated_descriptors"]
        if e["notes"]:
            desc_notes = f"{desc_notes} ({e['notes']})" if desc_notes else e["notes"]
        desc_notes = desc_notes[:27]
        print(f"{e['name_or_alias']:<18} {role_str:<22} {ex_str:<5} {rom_str:<5} {desc_notes:<28}")
    print("=" * 80)


def register_entity(
    db_path: str,
    chat_id: str,
    name_or_alias: str,
    verified_role: Optional[str] = None,
    associated_descriptors: Optional[str] = None,
    is_ex_partner: bool = False,
    is_romantic: bool = False,
    confidence: str = "verified",
    first_msg_id: Optional[int] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Register or update a third-party entity in the database."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    entity_id = re.sub(r'[^a-z0-9_]+', '_', name_or_alias.strip().lower()).strip('_')
    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()

    cur.execute("""
    INSERT INTO chat_entities
    (entity_id, chat_id, name_or_alias, verified_role, associated_descriptors,
     is_ex_partner, is_romantic, confidence, first_msg_id, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id, entity_id) DO UPDATE SET
        name_or_alias = excluded.name_or_alias,
        verified_role = coalesce(excluded.verified_role, chat_entities.verified_role),
        associated_descriptors = coalesce(excluded.associated_descriptors, chat_entities.associated_descriptors),
        is_ex_partner = excluded.is_ex_partner,
        is_romantic = excluded.is_romantic,
        confidence = excluded.confidence,
        first_msg_id = coalesce(excluded.first_msg_id, chat_entities.first_msg_id),
        notes = coalesce(excluded.notes, chat_entities.notes),
        updated_at = excluded.updated_at;
    """, (
        entity_id, chat_id, name_or_alias.strip(), verified_role,
        associated_descriptors, 1 if is_ex_partner else 0, 1 if is_romantic else 0,
        confidence, first_msg_id, notes, now_iso, now_iso
    ))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "entity_id": entity_id,
        "chat_id": chat_id,
        "name_or_alias": name_or_alias.strip(),
        "verified_role": verified_role,
        "associated_descriptors": associated_descriptors,
        "is_ex_partner": is_ex_partner,
        "is_romantic": is_romantic,
        "confidence": confidence,
        "first_msg_id": first_msg_id,
        "notes": notes
    }


def get_chat_descriptors(db_path: str, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve audited role/geographic descriptors and their cardinality."""
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    sql = """
    SELECT d.chat_id, coalesce(c.chat_name, d.chat_id), d.descriptor, d.cardinality,
           d.estimated_count, d.mapped_entity_ids, d.evidence_msg_ids, d.needs_recheck, d.audited_at
    FROM chat_descriptors d
    LEFT JOIN chats c ON d.chat_id = c.chat_id
    """
    params = []
    if chat_id:
        sql += " WHERE d.chat_id = ?"
        params.append(chat_id)
    sql += " ORDER BY d.descriptor ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "chat_id": r[0],
            "chat_name": r[1],
            "descriptor": r[2],
            "cardinality": r[3],
            "estimated_count": r[4],
            "mapped_entity_ids": r[5] or "",
            "evidence_msg_ids": r[6] or "",
            "needs_recheck": bool(r[7]),
            "audited_at": r[8]
        }
        for r in rows
    ]


def print_chat_descriptors(descriptors: List[Dict[str, Any]], chat_name: Optional[str] = None) -> None:
    """Print ASCII table of audited descriptors and cardinality."""
    print("\n" + "=" * 85)
    c_label = f" [Chat: {chat_name}]" if chat_name else ""
    print(f"🏷️  AUDITED DESCRIPTORS & ROLE CARDINALITY (K=1 vs K>1){c_label}")
    print("=" * 85)
    if not descriptors:
        print("No descriptors currently audited for this chat.")
        print("Run --audit-descriptor '<descriptor>' to run a lazy cardinality scan.")
        print("=" * 85)
        return

    print(f"{'Descriptor':<20} {'Cardinality':<18} {'Count':<6} {'Needs Recheck?':<15} {'Mapped Entities':<20}")
    print("-" * 85)
    for d in descriptors:
        recheck_str = "⚠️ YES" if d["needs_recheck"] else "OK"
        print(f"{d['descriptor']:<20} {d['cardinality']:<18} {d['estimated_count']:<6} {recheck_str:<15} {d['mapped_entity_ids']:<20}")
    print("=" * 85)


def audit_descriptor(
    db_path: str,
    descriptor: str,
    chat_id: Optional[str] = None
) -> Dict[str, Any]:
    """Run lazy cardinality audit on a descriptor (e.g. 'sister', 'US guy') for a given chat.

    Scans messages for mentions, checks pluralization/variations, correlates with registered entities,
    and classifies cardinality as SINGLETON_K1 vs POLYSEMOUS_K_GT_1.
    """
    conn = sqlite3.connect(db_path)
    ensure_entities_tables(conn)
    cur = conn.cursor()

    if not chat_id:
        cur.execute("SELECT chat_id FROM chats LIMIT 2;")
        c_rows = cur.fetchall()
        if len(c_rows) == 1:
            chat_id = c_rows[0][0]
        else:
            conn.close()
            raise ValueError("Multiple chats exist in database. Please specify chat via -C <chat_id>.")

    desc_clean = descriptor.strip().lower()
    tokens = [t for t in re.split(r'\W+', desc_clean) if t]

    matching_msgs = []
    try:
        fts_query = " OR ".join([f'"{tok}"' for tok in tokens if len(tok) > 2])
        if fts_query:
            cur.execute("""
            SELECT m.id, m.date, m.sender, m.text, m.thread_id
            FROM messages m
            JOIN messages_fts f ON m.id = f.rowid
            WHERE m.chat_id = ? AND messages_fts MATCH ?
            ORDER BY m.timestamp ASC;
            """, (chat_id, fts_query))
            matching_msgs = cur.fetchall()
    except Exception:
        matching_msgs = []

    if not matching_msgs:
        cur.execute("""
        SELECT m.id, m.date, m.sender, m.text, m.thread_id
        FROM messages m
        WHERE m.chat_id = ? AND lower(m.text) LIKE ?
        ORDER BY m.timestamp ASC;
        """, (chat_id, f"%{desc_clean}%"))
        matching_msgs = cur.fetchall()

    filtered_msgs = []
    plural_detected = False
    plural_evidence_ids = []

    cur.execute("SELECT entity_id, name_or_alias, associated_descriptors FROM chat_entities WHERE chat_id = ?;", (chat_id,))
    reg_entities = cur.fetchall()

    mapped_entities = set()
    for eid, ename, edesc in reg_entities:
        ename_lower = ename.lower()
        edesc_lower = (edesc or "").lower()
        if desc_clean in edesc_lower or ename_lower in desc_clean:
            mapped_entities.add(eid)

    # Identify base noun tokens and build targeted plural regex
    noun_tokens = [tok for tok in tokens if tok not in ("my", "the", "a", "an", "this", "that", "from", "in", "ten", "ta", "to", "mój", "moja", "moje")]
    plural_patterns = []
    for ntok in noun_tokens:
        plural_patterns.append(rf'\b(my|our|moja|moje|moi)\s+(?:\w+\s+)?{re.escape(ntok)}s\b')
        plural_patterns.append(rf'\b(my|our|moja|moje|moi)\s+(?:second|third|fourth|fifth|other|another|\d+(?:st|nd|rd|th)?|drug(?:a|i)|trzeci(?:a)?)\s+{re.escape(ntok)}\b')
        plural_patterns.append(rf'\b(two|three|four|five|several|multiple|both|dwie|dwaj|trzy|cztery|obaj)\s+(?:\w+\s+)?{re.escape(ntok)}s?\b')

    plural_regex = re.compile("|".join(plural_patterns), re.IGNORECASE) if plural_patterns else None

    evidence_ids = []
    for mid, mdate, msender, mtext, mth_id in matching_msgs:
        text_lower = mtext.lower()
        if any(tok in text_lower for tok in tokens) or desc_clean in text_lower:
            filtered_msgs.append((mid, mdate, msender, mtext, mth_id))
            evidence_ids.append(mid)

            if plural_regex and plural_regex.search(text_lower):
                plural_detected = True
                plural_evidence_ids.append(mid)

            for eid, ename, _ in reg_entities:
                if re.search(r'\b' + re.escape(ename.lower()) + r'\b', text_lower):
                    mapped_entities.add(eid)

    if len(mapped_entities) >= 2 or plural_detected:
        cardinality = "POLYSEMOUS_K_GT_1"
        est_count = max(2, len(mapped_entities))
    elif len(filtered_msgs) == 0:
        cardinality = "UNRESOLVED"
        est_count = 0
    else:
        cardinality = "SINGLETON_K1"
        est_count = 1

    now_iso = dt_module.datetime.now(dt_module.timezone.utc).isoformat()
    ev_ids_str = ",".join(str(x) for x in evidence_ids[:20])
    mapped_str = ",".join(sorted(mapped_entities))

    cur.execute("""
    INSERT INTO chat_descriptors
    (chat_id, descriptor, cardinality, estimated_count, mapped_entity_ids, evidence_msg_ids, needs_recheck, audited_at)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
    ON CONFLICT(chat_id, descriptor) DO UPDATE SET
        cardinality = excluded.cardinality,
        estimated_count = excluded.estimated_count,
        mapped_entity_ids = excluded.mapped_entity_ids,
        evidence_msg_ids = excluded.evidence_msg_ids,
        needs_recheck = 0,
        audited_at = excluded.audited_at;
    """, (chat_id, desc_clean, cardinality, est_count, mapped_str, ev_ids_str, now_iso))
    conn.commit()
    conn.close()

    return {
        "chat_id": chat_id,
        "descriptor": desc_clean,
        "cardinality": cardinality,
        "estimated_count": est_count,
        "plural_detected": plural_detected,
        "plural_evidence_msg_ids": plural_evidence_ids[:5],
        "mapped_entities": list(sorted(mapped_entities)),
        "total_mentions": len(filtered_msgs),
        "evidence_msg_ids": evidence_ids[:10],
        "sample_mentions": [
            {"id": m[0], "date": m[1][:10], "sender": m[2], "text": m[3][:120]}
            for m in filtered_msgs[:5]
        ]
    }


def print_descriptor_audit(audit: Dict[str, Any]) -> None:
    """Print ASCII report of lazy descriptor cardinality audit."""
    print("\n" + "=" * 80)
    print(f"🔬 LAZY DESCRIPTOR CARDINALITY AUDIT: '{audit['descriptor']}'")
    print(f"   Chat ID:          {audit['chat_id']}")
    print(f"   Total Mentions:   {audit['total_mentions']}")
    print(f"   Result:           {audit['cardinality']} (Estimated Count: {audit['estimated_count']})")
    print("=" * 80)

    if audit["mapped_entities"]:
        print(f"🔗 Mapped Known Entities: {', '.join(audit['mapped_entities'])}")
    if audit["plural_detected"]:
        print(f"⚠️  Plural language detected in messages: {audit['plural_evidence_msg_ids']}")

    print("\n📌 ACTIONABLE PROFILER DIRECTIVE:")
    if audit["cardinality"] == "SINGLETON_K1":
        print("   🟢 SINGLETON (K=1): Verified as a unique individual in this chat.")
        print("      Conversational inertia may link subsequent unanchored mentions to this entity.")
    elif audit["cardinality"] == "POLYSEMOUS_K_GT_1":
        print("   🔴 POLYSEMOUS (K>1): MULTIPLE INDIVIDUALS SHARE THIS ROLE OR DESCRIPTOR.")
        print("      CRITICAL INVARIANT: The agent is STRICTLY FORBIDDEN from attributing messages")
        print("      or traits using bare pronouns ('he', 'she') without a proper name anchor in N-5...N.")
    else:
        print("   ⚪ UNRESOLVED: Insufficient evidence in this chat stream to determine cardinality.")

    if audit["sample_mentions"]:
        print("\n📝 Sample Mentions in Chat:")
        for sm in audit["sample_mentions"]:
            print(f"   [#{sm['id']} | {sm['date']}] {sm['sender']}: {sm['text']}")
    print("=" * 80)
