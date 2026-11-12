"""Presentation, dashboard, and formatting views for Thread Checklist."""

import math
import sqlite3
from typing import List, Dict, Any, Optional
from checklist_engine.threads_db import ensure_thread_checklist_table


def print_thread_status(stats: Dict[str, Any]):
    """Print visually polished dashboard of thread checklist status."""
    chat_id = stats["chat_id"]
    total = stats["total"]
    completed = stats["completed"]
    pending = stats["pending"]
    skipped = stats["skipped"]
    na = stats["not_applicable"]
    pct = stats["progress_pct"]

    print("\n" + "=" * 80)
    print("🎯 THREAD FORENSIC AUDIT CHECKLIST (TRACK B - SUBSTANTIVE & INTENSIVE THREADS)")
    print(f"   Chat Scope: `{chat_id}`")
    print("=" * 80)

    if stats["is_waived"]:
        print("⚠️  STATUS: WAIVED / DISABLED (Safety Exemption Active)")
        print(f"   Reason: {stats['waiver_reason']}")
        print(f"   Audit gate is non-blocking. Re-enable with: python3 project/scripts/thread_checklist.py -C {chat_id} --enable")
        print("=" * 80)
        return

    bar_width = 36
    filled = int(round(bar_width * (pct / 100.0)))
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"Progress: [{bar}] {pct:5.1f}% ({stats['resolved']}/{total} resolved)")
    print(f"  • ✅ Completed Audits:   {completed:3d} threads")
    print(f"  • ⏳ Pending Audit:       {pending:3d} threads")
    print(f"  • ⏭️ Skipped / Bypassed:  {skipped:3d} threads")
    if na > 0:
        print(f"  • ⚪ Not Applicable:      {na:3d} threads")

    print("-" * 80)
    print("📡 BREAKDOWN BY DIAGNOSTIC RADAR / CATEGORY:")
    radar_labels = {
        "radar_1_anomalies": "⚡ Radar 1: Behavioral Anomalies & Interlocutor Shock",
        "radar_2_peak": "🎭 Radar 2: Acute Emotional Peaks (Grief, Euphoria, Rage)",
        "radar_3_advice_seeking": "💡 Radar 3: Confessions & Intimate Advice Dilemmas",
        "other_salient": "🌟 Other High-Salience Triaged Threads (Score >= 2.0)",
        "intensive_discussion": "📚 Top Substantive & Intensive Discussions"
    }
    for r_key, r_info in sorted(stats["radars"].items()):
        label = radar_labels.get(r_key, f"📡 {r_key}")
        r_tot = r_info["total"]
        r_comp = r_info.get("completed", 0)
        r_pend = r_info.get("pending", 0)
        status_icon = "✅" if r_pend == 0 and r_tot > 0 else "⏳"
        print(f"  {status_icon} {label:<58} | Done: {r_comp:2d}/{r_tot:2d} | Pend: {r_pend:2d}")

    if stats["next_pending"]:
        print("-" * 80)
        print("🔍 NEXT PRIORITY THREADS WAITING FOR AUDIT:")
        for idx, item in enumerate(stats["next_pending"], 1):
            tid = item["thread_id"]
            score = item["salience_score"]
            cat = item["primary_category"]
            src = item["radar_sources"]
            date = item["start_date"]
            msgs = item["message_count"]
            words = item["total_words"]
            print(f"  {idx}. [{date}] {tid:<26} (Score: {score:.1f} | {msgs} msgs, {words} words | {cat})")
            print(f"     Radars: {src}")
            print(f"     Inspect: python3 project/scripts/query_chat.py -t {tid}")

    print("=" * 80 + "\n")


def print_next_thread(conn: sqlite3.Connection, chat_id: str):
    """Fetch and print the next pending thread with metadata and instructions."""
    cur = conn.cursor()
    cur.execute("""
    SELECT t.thread_id, t.chat_id, t.start_date, t.end_date, t.message_count,
           t.participants, t.initiator, t.dialogue_text,
           tac.radar_sources, tac.salience_score, tac.primary_category,
           tac.status
    FROM thread_audit_checklist tac
    JOIN threads t ON tac.thread_id = t.thread_id
    WHERE tac.chat_id = ? AND tac.status = 'pending'
    ORDER BY tac.salience_score DESC, tac.total_words DESC
    LIMIT 1;
    """, (chat_id,))
    row = cur.fetchone()
    if not row:
        print(f"\n[✓] All substantive threads for chat '{chat_id}' are resolved! (0 pending threads).\n")
        return

    tid = row[0]
    c_id = row[1]
    start_d = row[2][:16].replace("T", " ") if row[2] else ""
    end_d = row[3][:16].replace("T", " ") if row[3] else ""
    msgs = row[4]
    parts = row[5]
    init = row[6]
    dialogue = row[7] or ""
    radars = row[8]
    score = row[9]
    cat = row[10]

    preview = dialogue[:1200]
    if len(dialogue) > 1200:
        preview += "\n... [Preview truncated. Run query_chat.py -t to view complete transcript] ..."

    print("\n" + "=" * 80)
    print(f"🎯 NEXT THREAD TO AUDIT: {tid}")
    print("=" * 80)
    print(f"  • Date Range:    {start_d} -> {end_d}")
    print(f"  • Participants:  {parts} (Initiator: {init})")
    print(f"  • Volume:        {msgs} messages | Salience Score: {score:.2f} | Category: {cat}")
    print(f"  • Radar Flags:   {radars}")
    print("-" * 80)
    print("📜 DIALOGUE TRANSCRIPT PREVIEW:")
    print("-" * 80)
    print(preview)
    print("-" * 80)
    print("🛠️ INVESTIGATION WORKFLOW & ACTIONS:")
    print(f"  1. Full Transcript:   python3 project/scripts/query_chat.py -t {tid}")
    print("  2. Context Window:    python3 project/scripts/query_chat.py --around <first_msg_id> -n 5")
    print(f"  3. Record Findings:   python3 project/scripts/thread_checklist.py -C {chat_id} --update {tid} \\")
    print("                        --set-status completed \\")
    print("                        --findings \"<Detailed psychological takeaways, defenses, attachment markers>\" \\")
    print(f"                        --quotes \"[#ID | {start_d[:10]}] \\\"verbatim quote\\\"\" \\")
    print("                        --tags \"#topic1 #defense #attachment\"")
    print("=" * 80 + "\n")


def print_delta_manifest(manifest: List[Dict[str, Any]], chat_id: str):
    """Print high-density delta manifest for prompt construction."""
    print("=" * 80)
    print(f"📋 DELTA TRIAGE MANIFEST: {len(manifest)} PENDING THREADS FOR CHAT '{chat_id}'")
    print("=" * 80)
    print("Instructions for Delta Subagent: Compare each thread summary against established baseline.")
    print("Filter into: (1) NOVELTY/ANOMALY (needs deep dive) vs (2) CORROBORATING/REDUNDANT.")
    print("-" * 80)

    for i, m in enumerate(manifest, 1):
        print(f"[{i:03d}] Thread {m['thread_id']} | Date: {m['date']} | Msgs: {m['messages']} | Score: {m['salience_score']:.1f} | Radars: {m['radar_sources']}")
        print(f"      Summary:  {m['summary']}")
        if m['candidate_entities'] and m['candidate_entities'] != "[]":
            print(f"      Entities: {m['candidate_entities']}")
        print(f"      Snippet:  \"{m['sample_snippet'][:120]}...\"\n")


def print_audited_evidence(
    evidence: List[Dict[str, Any]],
    chat_id: str,
    tag: Optional[str] = None,
    category: Optional[str] = None,
    part: int = 1,
    part_size: int = 8,
    show_all: bool = False
):
    """Print targeted bank of verified evidence with automatic pagination and context-safety guards."""
    total_items = len(evidence)
    scope_str = []
    if tag:
        scope_str.append(f"Tag: '{tag}'")
    if category:
        scope_str.append(f"Category: '{category}'")
    filter_label = f" [{', '.join(scope_str)}]" if scope_str else " [ALL THEMES]"

    if total_items == 0:
        print("=" * 80)
        print(f"🏛️ AUDITED FORENSIC EVIDENCE BANK (0 VERIFIED THREADS){filter_label} FOR CHAT '{chat_id}'")
        print("=" * 80)
        print("No matching verified evidence found in thread_audit_checklist.")
        print("-" * 80)
        return

    if show_all or total_items <= part_size:
        items_to_show = evidence
        part_badge = " [ALL ITEMS]" if show_all and total_items > part_size else ""
        total_parts = 1
        current_part = 1
        start_num = 1
        end_num = total_items
    else:
        total_parts = math.ceil(total_items / part_size)
        current_part = max(1, min(part, total_parts))
        start_idx = (current_part - 1) * part_size
        end_idx = start_idx + part_size
        items_to_show = evidence[start_idx:end_idx]
        part_badge = f" [PART {current_part}/{total_parts}]"
        start_num = start_idx + 1
        end_num = min(end_idx, total_items)

    print("=" * 80)
    print(f"🏛️ AUDITED FORENSIC EVIDENCE BANK ({total_items} TOTAL VERIFIED THREADS){filter_label}{part_badge}")
    print("=" * 80)
    print("Instructions for Main Agent: Integrate these verified findings into the current report section.")
    print("Cite exact [#ID | YYYY-MM-DD] anchors to substantiate the narrative.")
    if not show_all and total_items > part_size:
        print(f"📌 Showing items {start_num} to {end_num} of {total_items} (Context Safety Guard active).")
    print("-" * 80)

    start_counter = start_num if not show_all else 1
    for i, e in enumerate(items_to_show, start_counter):
        print(f"[{i:02d}] Thread `{e['thread_id']}` | Date: {e['date']} | Category: {e['category']} | Tags: {e['tags']}")
        if e['findings']:
            print(f"     Findings: {e['findings']}")
        if e['quotes']:
            print(f"     Quotes:   {e['quotes']}")
        if e['notes']:
            print(f"     Notes:    {e['notes']}")
        print()

    if not show_all and total_items > part_size:
        print("-" * 80)
        remaining = total_items - end_num
        tag_flag = f" --tag {tag}" if tag else ""
        cat_flag = f" --category {category}" if category else ""
        if current_part < total_parts:
            next_part = current_part + 1
            print(f"⚠️ CONTEXT SAFETY GUARD: {remaining} additional evidence items remain on subsequent parts.")
            print("   To inspect the next slice, run:")
            print(f"     python3 project/scripts/thread_checklist.py -C {chat_id} --export-evidence{tag_flag}{cat_flag} --part {next_part}")
            print(f"   Or pass '--all' to display all {total_items} items at once without pagination.")
        else:
            print(f"[✓] End of audited evidence for this query ({total_items} items across {total_parts} parts).")
        print("=" * 80)


def print_evidence_catalog(conn: sqlite3.Connection, chat_id: str):
    """Print high-level thematic catalog of all verified evidence to guide modular chapter drafting."""
    ensure_thread_checklist_table(conn)
    cur = conn.cursor()
    cur.execute("""
    SELECT primary_category, count(*), group_concat(thematic_tags, ' ')
    FROM thread_audit_checklist
    WHERE chat_id = ? AND status = 'completed'
      AND (findings_summary IS NOT NULL AND findings_summary NOT LIKE 'Theoretical Saturation%'
           OR key_quotes IS NOT NULL)
    GROUP BY primary_category;
    """, (chat_id,))
    rows = cur.fetchall()

    print("=" * 80)
    print(f"📚 AUDITED EVIDENCE THEMATIC CATALOG [Chat: {chat_id}]")
    print("=" * 80)
    if not rows:
        print("No verified forensic evidence recorded yet.")
        print("=" * 80)
        return

    print("Use these categories/tags to pull evidence modularly when drafting each chapter:")
    print("Example: python3 project/scripts/thread_checklist.py -C <cid> --export-evidence --tag <tag>")
    print("-" * 80)
    for cat, count, all_tags in rows:
        tags_set = set()
        if all_tags:
            for t in all_tags.split():
                if t.startswith("#"):
                    tags_set.add(t)
        tags_str = ", ".join(sorted(tags_set)[:8]) if tags_set else "no specific tags"
        print(f"  • Category: {cat:<22} | Threads: {count:>2} | Associated Tags: {tags_str}")
    print("=" * 80)
