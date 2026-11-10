#!/usr/bin/env python3
"""
Research Scratchpad & Evidence Ledger Generator.
Exports triaged dialogue threads (anomalies, emotional peaks, confessions/advice seeking,
substantive discussions, and burning days) from SQLite (chat.db) into structured
Markdown scratchpad files.

This prevents LLM context exhaustion by providing a persistent, file-based research ledger
where the agent audits high-salience interactions, records verbatim quotes and psychological
hypotheses, and tags findings before drafting final report chapters.
"""

import os
import sys
import math
import sqlite3
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # .agents/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # .agents
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "chat.db")


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h"


def format_dialogue_preview(dialogue_text: str, max_lines: int = 14) -> str:
    """Format dialogue lines into a readable quoted preview block."""
    if not dialogue_text:
        return "_No dialogue text recorded._"
    
    lines = dialogue_text.strip().splitlines()
    if len(lines) <= max_lines:
        formatted = "\n".join(f"> {line}" for line in lines)
        return formatted
    
    head_count = max_lines // 2
    tail_count = max_lines - head_count
    head_lines = lines[:head_count]
    tail_lines = lines[-tail_count:]
    
    preview = []
    for l in head_lines:
        preview.append(f"> {l}")
    preview.append(f"> ... [{len(lines) - max_lines} intermediate messages collapsed] ...")
    for l in tail_lines:
        preview.append(f"> {l}")
        
    return "\n".join(preview)


def fetch_threads_metadata(
    conn: sqlite3.Connection,
    thread_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Fetch thread metrics and dialogue texts for a given list of thread_ids."""
    if not thread_ids:
        return {}
    
    placeholders = ",".join(["?"] * len(thread_ids))
    sql = f"""
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id) as chat_name,
           t.start_date, t.end_date, t.message_count, t.participants, t.initiator,
           t.duration_seconds, t.dialogue_text, sum(m.word_count) as total_words
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    WHERE t.thread_id IN ({placeholders})
    GROUP BY t.thread_id;
    """
    cur = conn.cursor()
    cur.execute(sql, thread_ids)
    rows = cur.fetchall()
    
    res = {}
    for r in rows:
        res[r[0]] = {
            "thread_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "start_date": r[3][:16].replace("T", " "),
            "end_date": r[4][:16].replace("T", " "),
            "message_count": r[5],
            "participants": r[6],
            "initiator": r[7],
            "duration": format_duration(r[8] or 0),
            "dialogue_text": r[9] or "",
            "total_words": r[10] or 0
        }
    return res


def extract_triage_groups(
    conn: sqlite3.Connection,
    chat_id: Optional[str] = None,
    min_salience: float = 0.0,
    limit_per_category: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """Extract triaged threads categorized into Diagnostic Radars and other key buckets."""
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage'")
    if cur.fetchone()[0] == 0:
        return {
            "radar_1_anomalies": [],
            "radar_2_emotional_peaks": [],
            "radar_3_advice_seeking": [],
            "other_triaged": []
        }

    cur.execute("PRAGMA table_info(thread_triage)")
    cols = {col[1] for col in cur.fetchall()}
    has_atypical = "is_atypical" in cols
    has_peak = "emotional_peak" in cols
    has_advice = "is_advice_seeking" in cols

    atyp_sel = "tr.is_atypical" if has_atypical else "0"
    surp_sel = "tr.interlocutor_surprised" if has_atypical else "0"
    note_sel = "tr.anomaly_notes" if has_atypical else "''"
    peak_sel = "tr.emotional_peak" if has_peak else "'none'"
    adv_sel = "tr.is_advice_seeking" if has_advice else "0"

    sql = f"""
    SELECT tr.thread_id, tr.chat_id, tr.salience_score, tr.primary_category, tr.reason,
           {atyp_sel}, {surp_sel}, {note_sel}, {peak_sel}, {adv_sel}
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    WHERE tr.escalate = 1
    """
    params: List[Any] = []
    if chat_id:
        sql += " AND tr.chat_id = ? "
        params.append(chat_id)
    if min_salience > 0.0:
        sql += " AND tr.salience_score >= ? "
        params.append(min_salience)
        
    sql += " ORDER BY tr.salience_score DESC; "
    cur.execute(sql, params)
    rows = cur.fetchall()

    radar_1 = []
    radar_2 = []
    radar_3 = []
    other_triaged = []

    for r in rows:
        item = {
            "thread_id": r[0],
            "chat_id": r[1],
            "salience_score": r[2],
            "primary_category": r[3],
            "reason": r[4] or "",
            "is_atypical": r[5] or 0,
            "interlocutor_surprised": r[6] or 0,
            "anomaly_notes": r[7] or "",
            "emotional_peak": r[8] or "none",
            "is_advice_seeking": r[9] or 0
        }
        
        placed = False
        if item["is_atypical"] or item["interlocutor_surprised"]:
            radar_1.append(item)
            placed = True
        if item["emotional_peak"] != "none":
            radar_2.append(item)
            placed = True
        if item["is_advice_seeking"]:
            radar_3.append(item)
            placed = True
            
        if not placed:
            other_triaged.append(item)

    return {
        "radar_1_anomalies": radar_1[:limit_per_category],
        "radar_2_emotional_peaks": radar_2[:limit_per_category],
        "radar_3_advice_seeking": radar_3[:limit_per_category],
        "other_triaged": other_triaged[:limit_per_category]
    }


def extract_intensive_threads(
    conn: sqlite3.Connection,
    chat_id: Optional[str] = None,
    min_words: int = 60,
    min_messages: int = 8,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Extract top intensive discussions ranked by total volume and density."""
    cur = conn.cursor()
    sql = """
    SELECT t.thread_id, t.chat_id, coalesce(c.chat_name, t.chat_id) as chat_name,
           t.start_date, t.end_date, t.message_count, sum(m.word_count) as total_words,
           t.participants, t.initiator, t.duration_seconds
    FROM threads t
    JOIN messages m ON t.thread_id = m.thread_id
    LEFT JOIN chats c ON t.chat_id = c.chat_id
    """
    params: List[Any] = []
    if chat_id:
        sql += " WHERE t.chat_id = ? "
        params.append(chat_id)
        
    sql += """
    GROUP BY t.thread_id
    HAVING t.message_count >= ? AND total_words >= ?
    ORDER BY total_words DESC
    LIMIT ?;
    """
    params.extend([min_messages, min_words, limit])
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    return [
        {
            "thread_id": r[0],
            "chat_id": r[1],
            "chat_name": r[2],
            "start_date": r[3][:16].replace("T", " "),
            "end_date": r[4][:16].replace("T", " "),
            "message_count": r[5],
            "total_words": r[6] or 0,
            "participants": r[7],
            "initiator": r[8],
            "duration": format_duration(r[9] or 0)
        }
        for r in rows
    ]


def fetch_entities_and_descriptors(
    conn: sqlite3.Connection,
    chat_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch registered chat entities and audited descriptors."""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chat_entities';")
    has_ent = cur.fetchone()[0] > 0
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='chat_descriptors';")
    has_desc = cur.fetchone()[0] > 0

    entities = []
    if has_ent:
        sql = """
        SELECT name_or_alias, verified_role, is_ex_partner, is_romantic, associated_descriptors, notes, first_msg_id
        FROM chat_entities
        """
        params: List[Any] = []
        if chat_id:
            sql += " WHERE chat_id = ?"
            params.append(chat_id)
        sql += " ORDER BY name_or_alias ASC"
        cur.execute(sql, params)
        for r in cur.fetchall():
            entities.append({
                "name": r[0],
                "role": r[1] or "",
                "is_ex": bool(r[2]),
                "is_romantic": bool(r[3]),
                "descriptors": r[4] or "",
                "notes": r[5] or "",
                "first_msg": r[6]
            })

    descriptors = []
    if has_desc:
        sql = """
        SELECT descriptor, cardinality, estimated_count, mapped_entity_ids, needs_recheck, evidence_msg_ids
        FROM chat_descriptors
        """
        params = []
        if chat_id:
            sql += " WHERE chat_id = ?"
            params.append(chat_id)
        sql += " ORDER BY descriptor ASC"
        cur.execute(sql, params)
        for r in cur.fetchall():
            descriptors.append({
                "descriptor": r[0],
                "cardinality": r[1],
                "count": r[2],
                "mapped_entities": r[3] or "",
                "needs_recheck": bool(r[4]),
                "evidence_ids": r[5] or ""
            })

    return entities, descriptors


def render_thread_entry(
    triage_info: Optional[Dict[str, Any]],
    meta_info: Dict[str, Any],
    radar_tag: str,
    include_dialogue: bool = True
) -> str:
    """Render a single thread entry with metadata, dialogue preview, and empty research template."""
    thread_id = meta_info["thread_id"]
    date_str = meta_info["start_date"]
    chat_name = meta_info["chat_name"]
    msgs = meta_info["message_count"]
    words = meta_info["total_words"]
    participants = meta_info["participants"]
    
    badges = []
    if triage_info:
        if triage_info.get("is_atypical"):
            badges.append("⚡ [ATYPICAL_BEHAVIOR]")
        if triage_info.get("interlocutor_surprised"):
            badges.append("😲 [INTERLOCUTOR_SHOCK]")
        peak = triage_info.get("emotional_peak", "none")
        if peak != "none":
            badges.append(f"🔥 [{peak.upper()}]")
        if triage_info.get("is_advice_seeking"):
            badges.append("💡 [CONFESSION_OR_ADVICE_SEEKING]")
        cat = triage_info.get("primary_category", "general")
        badges.append(f"🏷️ [{cat}]")
        score = triage_info.get("salience_score", 0.0)
        badges.append(f"⭐ Salience: {score:.1f}")
    else:
        badges.append(f"💬 [INTENSIVE_DISCUSSION | {words:,} words]")
        
    badge_line = " ".join(badges)
    reason = triage_info.get("reason", "") if triage_info else "High-volume substantive dialogue thread."
    notes = triage_info.get("anomaly_notes", "") if triage_info else ""
    
    out = []
    out.append(f"### `{thread_id}` | {date_str} | Chat: {chat_name}")
    out.append(f"**Diagnostic Class:** `{radar_tag}` | {badge_line}")
    out.append(f"- **Participants:** {participants} (Initiator: {meta_info.get('initiator', 'Unknown')}) | **Length:** {msgs} msgs, {words:,} words ({meta_info.get('duration', 'N/A')})")
    out.append(f"- **Triage Reason:** {reason}")
    if notes:
        out.append(f"- **System-1 Radar Notes:** _{notes}_")
        
    if include_dialogue and meta_info.get("dialogue_text"):
        out.append("\n**Dialogue Context & Text Preview:**")
        out.append(format_dialogue_preview(meta_info["dialogue_text"]))
        
    out.append("\n**Profiler Working Notes (To be filled during batch investigation):**")
    out.append("- [ ] **Investigated:** No")
    out.append("- **Trigger & Context:** <!-- What provoked this exchange? Look back N-5 -->")
    out.append("- **Verbatim Anchors:** <!-- Exact quote with [#ID | YYYY-MM-DD] -->")
    out.append("- **Psychological Dynamics & Defenses:** <!-- Defense mechanisms, blind spots, emotional roots -->")
    out.append("- **Thematic Tags:** <!-- e.g. #work #attachment #defense_mechanism #family #unspoken_need -->")
    out.append("- **Working Hypotheses:** <!-- Emergent finding to integrate into report chapter -->")
    out.append("\n---\n")
    
    return "\n".join(out)


def generate_scratchpad(
    db_path: str,
    output_dir: str,
    chat_id: Optional[str] = None,
    min_salience: float = 0.0,
    limit_per_category: int = 60,
    include_dialogue: bool = True
) -> Dict[str, Any]:
    """Generate complete research scratchpad markdown files in output_dir."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    os.makedirs(output_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # 1. Extract triage groups
    triage_groups = extract_triage_groups(
        conn, chat_id=chat_id, min_salience=min_salience, limit_per_category=limit_per_category
    )
    
    # 2. Extract intensive threads
    intensive_threads = extract_intensive_threads(
        conn, chat_id=chat_id, limit=limit_per_category
    )

    # Collect all unique thread IDs
    all_triage_items: Dict[str, Dict[str, Any]] = {}
    for grp_items in triage_groups.values():
        for it in grp_items:
            all_triage_items[it["thread_id"]] = it
            
    thread_ids_to_fetch = set(all_triage_items.keys())
    for it in intensive_threads:
        thread_ids_to_fetch.add(it["thread_id"])
        
    # Fetch thread metadata & dialogues
    metadata_map = fetch_threads_metadata(conn, list(thread_ids_to_fetch))

    # Fetch registered entities and audited descriptors
    entities, descriptors = fetch_entities_and_descriptors(conn, chat_id=chat_id)
    conn.close()

    # Track seen threads to avoid duplicating the full dialogue block if in multiple sections
    rendered_in_ledger: Set[str] = set()

    ledger_path = os.path.join(output_dir, "evidence_ledger.md")
    hypothesis_path = os.path.join(output_dir, "hypothesis_matrix.md")

    # Generate evidence_ledger.md
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("# Forensic Research Scratchpad & Evidence Ledger\n\n")
        f.write(f"> **Database Source:** `{os.path.basename(db_path)}`  \n")
        f.write(f"> **Generated At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"> **Filter Chat:** `{chat_id or 'All Chats'}`  \n")
        f.write("> **Purpose:** Persistent investigation ledger for batch-auditing dialogue anomalies, emotional peaks, advice dilemmas, and substantive discussions. Agent records verbatim quotes, psychological mechanisms, and thematic tags here BEFORE drafting final report chapters, preventing context exhaustion.\n\n")
        
        f.write("## Table of Ledger Sections\n\n")
        f.write("- [0. Third-Party Entities & Role Descriptors](#0-third-party-entities--role-descriptors)\n")
        f.write("- [1. Radar 1: Behavioral Anomalies & Interlocutor Shock](#1-radar-1-behavioral-anomalies--interlocutor-shock)\n")
        f.write("- [2. Radar 2: Acute Emotional Peaks & Dyadic Gravity](#2-radar-2-acute-emotional-peaks--dyadic-gravity)\n")
        f.write("- [3. Radar 3: Confessions & Advice Seeking](#3-radar-3-confessions--advice-seeking)\n")
        f.write("- [4. Other High-Salience Triaged Threads](#4-other-high-salience-triaged-threads)\n")
        f.write("- [5. Top Substantive & Intensive Discussions](#5-top-substantive--intensive-discussions)\n\n")
        f.write("---\n\n")

        # Section 0: Entities and Descriptors
        f.write("## 0. Third-Party Entities & Role Descriptors\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> **Anti-Conflation & Cardinality Safeguards:**\n")
        f.write("> - **Hermetic Chat-Level Scoping:** All entities and descriptors are strictly scoped to this chat. Never transpose attributes across different files.\n")
        f.write("> - **Polysemous Roles (K > 1):** Descriptors marked `POLYSEMOUS_K_GT_1` represent roles shared by multiple individuals. Attributing messages or traits using bare pronouns (*he*, *she*) without a verified proper name anchor in $N-5 \\dots N$ is strictly prohibited.\n")
        f.write("> - **Next-Turn Proof ($N+1 \\dots N+5$):** If an interlocutor refutes an attribution (e.g. *\"not my ex btw\"*), the proposition cannot be adopted as truth.\n\n")

        f.write("### 👥 Registered Third-Party Entities\n\n")
        if not entities:
            f.write("_No third-party entities registered yet. Use `query_chat.py --register-entity <name> --role <role>` to register._\n\n")
        else:
            f.write("| Name / Alias | Verified Role | Ex-Partner? | Romantic? | Associated Descriptors / Traits | Notes | First Msg Anchor |\n")
            f.write("| :--- | :--- | :---: | :---: | :--- | :--- | :--- |\n")
            for e in entities:
                ex_tag = "YES" if e["is_ex"] else "no"
                rom_tag = "YES" if e["is_romantic"] else "no"
                first_msg = f"[#{e['first_msg']}]" if e["first_msg"] else "-"
                f.write(f"| **{e['name']}** | {e['role']} | {ex_tag} | {rom_tag} | {e['descriptors']} | {e['notes']} | {first_msg} |\n")
            f.write("\n")

        f.write("### 🏷️ Audited Descriptors & Role Cardinality\n\n")
        if not descriptors:
            f.write("_No descriptors audited yet. Use `query_chat.py --audit-descriptor <descriptor>` on demand._\n\n")
        else:
            f.write("| Descriptor | Cardinality Class | Estimated Count | Needs Recheck? | Mapped Entity IDs | Sample Evidence Msg IDs |\n")
            f.write("| :--- | :---: | :---: | :---: | :--- | :--- |\n")
            for d in descriptors:
                recheck_tag = "⚠️ **YES**" if d["needs_recheck"] else "OK"
                card_badge = f"`{d['cardinality']}`"
                f.write(f"| **{d['descriptor']}** | {card_badge} | {d['count']} | {recheck_tag} | {d['mapped_entities'] or '-'} | {d['evidence_ids'] or '-'} |\n")
            f.write("\n")

        f.write("---\n\n")

        # Section 1: Radar 1
        f.write("## 1. Radar 1: Behavioral Anomalies & Interlocutor Shock\n\n")
        f.write("_Contains threads flagged for deviant behavior (`is_atypical`) or conversational dissonance where interlocutor expressed shock/disbelief (`interlocutor_surprised`)._\n\n")
        radar1_list = triage_groups["radar_1_anomalies"]
        if not radar1_list:
            f.write("_No threads flagged in Radar 1._\n\n")
        else:
            for item in radar1_list:
                t_id = item["thread_id"]
                if t_id in metadata_map:
                    f.write(render_thread_entry(item, metadata_map[t_id], "RADAR_1_ANOMALY", include_dialogue))
                    rendered_in_ledger.add(t_id)

        # Section 2: Radar 2
        f.write("\n## 2. Radar 2: Acute Emotional Peaks & Dyadic Gravity\n\n")
        f.write("_Contains moments of affective extremes (`profound_sadness`, `euphoric_joy`, `intense_rage`), capturing direct emotionality and flat-affect grief/consoling._\n\n")
        radar2_list = triage_groups["radar_2_emotional_peaks"]
        if not radar2_list:
            f.write("_No threads flagged in Radar 2._\n\n")
        else:
            for item in radar2_list:
                t_id = item["thread_id"]
                if t_id in metadata_map:
                    # If already rendered in section 1, avoid full duplicate dialogue to save file size
                    inc_dlg = include_dialogue and (t_id not in rendered_in_ledger)
                    f.write(render_thread_entry(item, metadata_map[t_id], "RADAR_2_EMOTIONAL_PEAK", inc_dlg))
                    rendered_in_ledger.add(t_id)

        # Section 3: Radar 3
        f.write("\n## 3. Radar 3: Confessions & Advice Seeking\n\n")
        f.write("_Contains instances where psychological defenses drop to seek advice, disclose intimate dilemmas, or voice moral impasses._\n\n")
        radar3_list = triage_groups["radar_3_advice_seeking"]
        if not radar3_list:
            f.write("_No threads flagged in Radar 3._\n\n")
        else:
            for item in radar3_list:
                t_id = item["thread_id"]
                if t_id in metadata_map:
                    inc_dlg = include_dialogue and (t_id not in rendered_in_ledger)
                    f.write(render_thread_entry(item, metadata_map[t_id], "RADAR_3_ADVICE_SEEKING", inc_dlg))
                    rendered_in_ledger.add(t_id)

        # Section 4: Other Triaged
        f.write("\n## 4. Other High-Salience Triaged Threads\n\n")
        f.write("_High-salience threads qualified by System-1 decider (e.g. relational milestones, career turns, quiet disclosures)._\n\n")
        other_list = triage_groups["other_triaged"]
        if not other_list:
            f.write("_No other triaged threads in this category._\n\n")
        else:
            for item in other_list:
                t_id = item["thread_id"]
                if t_id in metadata_map and t_id not in rendered_in_ledger:
                    f.write(render_thread_entry(item, metadata_map[t_id], "TRIAGED_SALIENCE", include_dialogue))
                    rendered_in_ledger.add(t_id)

        # Section 5: Intensive Discussions
        f.write("\n## 5. Top Substantive & Intensive Discussions\n\n")
        f.write("_Longest, most cognitively dense discussions ranked by total conversational volume, intellectual exchange, and sustained interaction._\n\n")
        if not intensive_threads:
            f.write("_No intensive threads identified._\n\n")
        else:
            for it in intensive_threads:
                t_id = it["thread_id"]
                if t_id in metadata_map and t_id not in rendered_in_ledger:
                    triage_meta = all_triage_items.get(t_id)
                    f.write(render_thread_entry(triage_meta, metadata_map[t_id], "INTENSIVE_DISCUSSION", include_dialogue))
                    rendered_in_ledger.add(t_id)

    # Generate hypothesis_matrix.md
    with open(hypothesis_path, "w", encoding="utf-8") as f:
        f.write("# Working Hypothesis Matrix & Tag Index\n\n")
        f.write("> **Purpose:** Cross-cutting synthesis board. As the agent audits threads in `evidence_ledger.md`, it records emergent hypotheses here grouped by thematic chapters (Spheres A–F, OCEAN, Attachment, Operational Manual).\n\n")
        f.write("## Entity Disambiguation Baseline\n\n")
        if entities:
            ent_names = ", ".join(f"`{e['name']}` ({e['role']})" for e in entities)
            f.write(f"- **Registered Entities ({len(entities)}):** {ent_names}\n")
        else:
            f.write("- **Registered Entities:** None recorded yet.\n")
        if descriptors:
            desc_items = ", ".join(f"`{d['descriptor']}` ({d['cardinality']})" for d in descriptors)
            f.write(f"- **Audited Descriptors ({len(descriptors)}):** {desc_items}\n")
        else:
            f.write("- **Audited Descriptors:** None recorded yet.\n")
        f.write("\n---\n\n")
        f.write("## Thematic Chapter Mapping\n\n")
        f.write("| Chapter / Sphere | Relevant Ledger Tags | Emergent Core Hypotheses & Evidence Links |\n")
        f.write("| :--- | :--- | :--- |\n")
        f.write("| **Biographical Dossier & Roots** | `#origin_story` `#parental_imprint` `#crucible` | _Record emerging origin notes and chronological anchors..._ |\n")
        f.write("| **Cast of Characters** | `#family` `#romantic_partner` `#friend` `#authority` | _Map recurring figures and dynamic stances..._ |\n")
        f.write("| **Sphere A: Social Matrix & Friends** | `#friendship` `#altruism` `#door_slam` `#cadence` | _Synthesize friendship patterns, offline cadence, helping style..._ |\n")
        f.write("| **Sphere B: Work, Ambition & Finances** | `#work_ethic` `#unfulfilled_ambition` `#money` | _Catalogue dropped projects, grinders vs slackers, money stance..._ |\n")
        f.write("| **Sphere C: Worldview & AI** | `#politics` `#ai_stance` `#debate_style` | _Ideology, empirical logic vs moralism, AI perspective..._ |\n")
        f.write("| **Sphere D: Family Roots & Domestic Order**| `#parents` `#cleanliness` `#domestic_order` | _Orderliness vs chaos, parentification, domestic environment..._ |\n")
        f.write("| **Sphere E: Romantic Attachment** | `#attachment` `#deactivating_strategy` `#intimacy` | _Attachment style diagnosis, push-pull dynamics..._ |\n")
        f.write("| **Sphere F: Leisure, Sports & Animals** | `#hobbies` `#sports` `#vacation` `#animals` | _Free time restoration, physical culture, pet empathy..._ |\n")
        f.write("| **Big Five (OCEAN) Architecture** | `#ocean_O` `#ocean_C` `#ocean_E` `#ocean_A` `#ocean_N` | _Trait estimates and cognitive processing styles..._ |\n")
        f.write("| **Operational User Manual** | `#blind_spot` `#trigger` `#unspoken_need` `#communication` | _Red buttons, unspoken hunger, dos and don'ts..._ |\n\n")
        f.write("## Quick Index of Audited Threads\n\n")
        f.write("_Populate as threads are audited in `evidence_ledger.md` (e.g. `[#T102] -> #work_ethic, #unfulfilled_ambition: Fear of public evaluation stalled university transfer`)._\n\n")

    return {
        "output_dir": output_dir,
        "evidence_ledger": ledger_path,
        "hypothesis_matrix": hypothesis_path,
        "total_unique_threads": len(rendered_in_ledger),
        "radar_1_count": len(triage_groups["radar_1_anomalies"]),
        "radar_2_count": len(triage_groups["radar_2_emotional_peaks"]),
        "radar_3_count": len(triage_groups["radar_3_advice_seeking"]),
        "other_triaged_count": len(triage_groups["other_triaged"]),
        "intensive_count": len(intensive_threads)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate Markdown Research Scratchpad & Evidence Ledger from SQLite chat data."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        required=True,
        help="Target scratchpad directory (e.g. reports/<subject>_scratchpad/)"
    )
    parser.add_argument(
        "--chat",
        type=str,
        help="Optional filter by chat_id or chat_name"
    )
    parser.add_argument(
        "--min-salience",
        type=float,
        default=0.0,
        help="Minimum triage salience score (default: 0.0)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=60,
        help="Maximum threads to include per category/radar (default: 60)"
    )
    parser.add_argument(
        "--no-dialogue",
        action="store_true",
        help="Exclude dialogue text preview to produce a compact index only"
    )

    args = parser.parse_args()

    # Safety check: enforce stateless project principle
    abs_out = os.path.abspath(args.output_dir)
    if abs_out.startswith(PROJECT_DIR):
        print(f"[!] ERROR: Target directory '{args.output_dir}' is inside the agent package ('.agents/').")
        print("    Per the Stateless Agent Principle, all reports, databases, and scratchpads")
        print("    must be stored outside the agent package (e.g. in workspace root 'reports/<subject>_scratchpad/').")
        sys.exit(1)

    try:
        stats = generate_scratchpad(
            db_path=args.db,
            output_dir=args.output_dir,
            chat_id=args.chat,
            min_salience=args.min_salience,
            limit_per_category=args.limit,
            include_dialogue=not args.no_dialogue
        )
        print("\n" + "=" * 65)
        print("📝 RESEARCH SCRATCHPAD & EVIDENCE LEDGER GENERATED")
        print("=" * 65)
        print(f"Target Directory:      {stats['output_dir']}")
        print(f"Evidence Ledger:       {stats['evidence_ledger']}")
        print(f"Hypothesis Matrix:     {stats['hypothesis_matrix']}")
        print(f"Total Unique Threads:  {stats['total_unique_threads']}")
        print(f"  - Radar 1 (Anomalies):       {stats['radar_1_count']}")
        print(f"  - Radar 2 (Emotional Peaks): {stats['radar_2_count']}")
        print(f"  - Radar 3 (Advice/Dilemmas): {stats['radar_3_count']}")
        print(f"  - Other Triaged Salient:     {stats['other_triaged_count']}")
        print(f"  - Intensive Discussions:     {stats['intensive_count']}")
        print("=" * 65)
        print("\nNext step: The agent batch-audits the ledger, fills in working notes & tags,")
        print("and references these hypotheses when drafting modular report sections.")
    except Exception as e:
        print(f"[!] Error generating research scratchpad: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
