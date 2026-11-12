"""Reduction and diagnostic radar reporting."""

import sqlite3
from typing import Optional


def print_reduction_report(conn: sqlite3.Connection, chat_id: Optional[str] = None):
    """Generate and display comprehensive reduction and diagnostic radar statistics."""
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='thread_triage';")
    if cur.fetchone()[0] == 0:
        c_label = f" [Chat: {chat_id}]" if chat_id else ""
        print("\n" + "=" * 80)
        print(f"🎯 SYSTEM 1 TRIAGE REDUCTION & DIAGNOSTIC REPORT{c_label}")
        print("=" * 80)
        print("[!] No threads have been triaged yet (thread_triage table does not exist).")
        cid_flag = f" -C {chat_id}" if chat_id else ""
        print("    To run System-1 triage, execute:")
        print(f"    python3 project/scripts/triage_threads.py{cid_flag}")
        print("=" * 80 + "\n")
        return

    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='threads';")
    if cur.fetchone()[0] == 0:
        print("[!] Error: threads table does not exist in the database.")
        return

    t_where = " WHERE chat_id = ?" if chat_id else ""
    t_params = (chat_id,) if chat_id else ()

    cur.execute(f"SELECT count(*) FROM threads{t_where}", t_params)
    total_threads = cur.fetchone()[0]

    cur.execute(f"SELECT count(*) FROM thread_triage{t_where}", t_params)
    total_triaged = cur.fetchone()[0]

    if total_triaged == 0:
        c_label = f" [Chat: {chat_id}]" if chat_id else ""
        print("\n" + "=" * 80)
        print(f"🎯 SYSTEM 1 TRIAGE REDUCTION & DIAGNOSTIC REPORT{c_label}")
        print("=" * 80)
        print(f"Total Threads in Database:   {total_threads:,}")
        print("Threads Evaluated by Triage: 0")
        print("[!] No threads have been triaged yet for this chat.")
        cid_flag = f" -C {chat_id}" if chat_id else ""
        print("    To run System-1 triage, execute:")
        print(f"    python3 project/scripts/triage_threads.py{cid_flag}")
        print("=" * 80 + "\n")
        return

    def scope_where(extra_cond: Optional[str] = None) -> tuple:
        conds = []
        params = []
        if chat_id:
            conds.append("chat_id = ?")
            params.append(chat_id)
        if extra_cond:
            conds.append(extra_cond)
        clause = f" WHERE {' AND '.join(conds)}" if conds else ""
        return clause, tuple(params)

    # Escalated count
    cl, pr = scope_where("escalate = 1")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    escalated_count = cur.fetchone()[0]
    rejected_count = total_triaged - escalated_count

    # Radar 1: Anomalies & Shock
    cl, pr = scope_where("is_atypical = 1")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    atypical_count = cur.fetchone()[0]

    cl, pr = scope_where("interlocutor_surprised = 1")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    surprised_count = cur.fetchone()[0]

    # Radar 2: Emotional Peaks
    cl, pr = scope_where("emotional_peak != 'none'")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    peaks_count = cur.fetchone()[0]

    cur.execute(f"SELECT emotional_peak, count(*) FROM thread_triage{cl} GROUP BY emotional_peak", pr)
    peak_map = dict(cur.fetchall())
    sadness_count = peak_map.get("profound_sadness", 0)
    joy_count = peak_map.get("euphoric_joy", 0)
    rage_count = peak_map.get("intense_rage", 0)

    # Radar 3: Advice Seeking & Confessions
    cl, pr = scope_where("is_advice_seeking = 1")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    advice_count = cur.fetchone()[0]

    # Radar 4: Third-Party Mentions
    cl, pr = scope_where("mentions_third_party = 1")
    cur.execute(f"SELECT count(*) FROM thread_triage{cl}", pr)
    third_party_count = cur.fetchone()[0]

    # Word counts
    if chat_id:
        cur.execute("""
        SELECT sum(m.word_count)
        FROM messages m
        WHERE m.thread_id IN (SELECT thread_id FROM thread_triage WHERE chat_id = ?)
        """, (chat_id,))
    else:
        cur.execute("""
        SELECT sum(m.word_count)
        FROM messages m
        WHERE m.thread_id IN (SELECT thread_id FROM thread_triage)
        """)
    triaged_words = cur.fetchone()[0] or 0

    if chat_id:
        cur.execute("""
        SELECT sum(m.word_count)
        FROM messages m
        WHERE m.thread_id IN (SELECT thread_id FROM thread_triage WHERE escalate = 1 AND chat_id = ?)
        """, (chat_id,))
    else:
        cur.execute("""
        SELECT sum(m.word_count)
        FROM messages m
        WHERE m.thread_id IN (SELECT thread_id FROM thread_triage WHERE escalate = 1)
        """)
    escalated_words = cur.fetchone()[0] or 0

    reduction_thread_pct = (rejected_count / total_triaged * 100.0) if total_triaged > 0 else 0.0
    word_reduction_pct = ((triaged_words - escalated_words) / triaged_words * 100.0) if triaged_words > 0 else 0.0

    c_label = f" [Chat: {chat_id}]" if chat_id else ""
    print("\n" + "=" * 80)
    print(f"🎯 SYSTEM 1 TRIAGE (DECIDER / ROUTER) REDUCTION & DIAGNOSTIC REPORT{c_label}")
    print("=" * 80)
    cov_pct = (total_triaged / total_threads * 100.0) if total_threads > 0 else 0.0
    print(f"Total Threads in Database:      {total_threads:,}")
    print(f"Threads Evaluated by Triage:    {total_triaged:,} ({cov_pct:.1f}% coverage)")
    print("-" * 80)
    print(f"🟢 Threads Escalated to LLM:    {escalated_count:,} ({escalated_count / total_triaged * 100.0:.1f}%)")
    print(f"🔴 Threads Filtered as Noise:   {rejected_count:,} ({rejected_count / total_triaged * 100.0:.1f}%)")
    print(f"📉 Thread Volume Reduction:      {reduction_thread_pct:.1f}%")
    print(f"📉 Word / Token Reduction:       {word_reduction_pct:.1f}% ({triaged_words:,} words -> {escalated_words:,} words)")
    print("-" * 80)
    print("🔍 DIAGNOSTIC RADARS OVERVIEW:")
    print(f"  ⚡ Radar 1 (Anomalies & Shocks):      {atypical_count + surprised_count} flags (Atypical: {atypical_count}, Surprised: {surprised_count})")
    print(f"  🎭 Radar 2 (Acute Emotional Peaks):    {peaks_count} threads (😢 Sadness/Grief: {sadness_count}, 🎉 Joy/Euphoria: {joy_count}, 😡 Rage: {rage_count})")
    print(f"  💡 Radar 3 (Confessions & Advice):     {advice_count} threads")
    print(f"  👤 Radar 4 (Third-Party Mentions):     {third_party_count} threads")
    print("=" * 80)

    cat_where = " WHERE chat_id = ?" if chat_id else ""
    cat_params = (chat_id,) if chat_id else ()
    cur.execute(f"""
    SELECT primary_category, count(*), sum(case when escalate = 1 then 1 else 0 end), avg(salience_score)
    FROM thread_triage
    {cat_where}
    GROUP BY primary_category
    ORDER BY count(*) DESC
    """, cat_params)
    rows = cur.fetchall()

    print("\n📊 CATEGORY BREAKDOWN:")
    print(f"{'Category':<32} {'Total':<8} {'Escalated':<12} {'Filtered':<10} {'Avg Score'}")
    print("-" * 80)
    for cat, total, esc, avg_score in rows:
        filt = total - esc
        print(f"{cat:<32} {total:<8} {esc:<12} {filt:<10} {avg_score:.2f}")

    # Showcase Radar 2: Acute Emotional Peaks
    peak_where = " WHERE tr.emotional_peak != 'none'"
    peak_params = []
    if chat_id:
        peak_where += " AND t.chat_id = ?"
        peak_params.append(chat_id)

    cur.execute(f"""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.emotional_peak,
           tr.reason, substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    {peak_where}
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 4
    """, tuple(peak_params))
    peak_samples = cur.fetchall()

    if peak_samples:
        print("\n🎭 ACUTE EMOTIONAL PEAKS (Grief, Euphoria, Rage & Empathetic Consoling):")
        print("-" * 80)
        for pid, pdate, pmsgs, pscore, ptype, preason, ptext in peak_samples:
            icon = "😢" if ptype == "profound_sadness" else ("🎉" if ptype == "euphoric_joy" else "😡")
            print(f"[{pdate}] Thread {pid} | Msgs: {pmsgs} | Score: {pscore:.1f} | {icon} {ptype.upper()}")
            print(f"  Reason:  {preason}")
            teaser = ptext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {pid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

    # Showcase Radar 3: Confessions & Advice Seeking
    adv_where = " WHERE tr.is_advice_seeking = 1"
    adv_params = []
    if chat_id:
        adv_where += " AND t.chat_id = ?"
        adv_params.append(chat_id)

    cur.execute(f"""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           tr.reason, substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    {adv_where}
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 3
    """, tuple(adv_params))
    advice_samples = cur.fetchall()

    if advice_samples:
        print("💡 INTIMATE CONFESSIONS & ADVICE SEEKING (Life Dilemmas & Decision Impasses):")
        print("-" * 80)
        for aid, adate, amsgs, ascore, acat, areason, atext in advice_samples:
            print(f"[{adate}] Thread {aid} | Msgs: {amsgs} | Score: {ascore:.1f} | Cat: {acat}")
            print(f"  Reason:  {areason}")
            teaser = atext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {aid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

    # Showcase Radar 1: Anomalies & Shock
    anom_where = " WHERE (tr.is_atypical = 1 OR tr.interlocutor_surprised = 1)"
    anom_params = []
    if chat_id:
        anom_where += " AND t.chat_id = ?"
        anom_params.append(chat_id)

    cur.execute(f"""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           tr.is_atypical, tr.interlocutor_surprised, tr.anomaly_notes, tr.reason,
           substr(t.dialogue_text, 1, 120)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    {anom_where}
    ORDER BY tr.salience_score DESC, t.message_count ASC
    LIMIT 3
    """, tuple(anom_params))
    anomalies = cur.fetchall()

    if anomalies:
        print("⚡ BEHAVIORAL ANOMALIES & INTERLOCUTOR SHOCKS:")
        print("-" * 80)
        for aid, adate, amsgs, ascore, acat, atyp, asurp, anotes, areason, atext in anomalies:
            flags = []
            if atyp:
                flags.append("⚡ ATYPICAL")
            if asurp:
                flags.append("😲 SURPRISED")
            flag_str = " | ".join(flags)
            print(f"[{adate}] Thread {aid} | Msgs: {amsgs} | Score: {ascore:.1f} | {flag_str}")
            if anotes:
                print(f"  Notes:   {anotes}")
            print(f"  Reason:  {areason}")
            teaser = atext.strip().replace(chr(10), " ")[:70]
            print(f"  Audit:   python3 project/scripts/query_chat.py -t {aid} (or --around <msg_id> -n 5)")
            print(f"  Teaser:  \"{teaser}...\" [UNVERIFIED RADAR HIT - DO NOT CITE WITHOUT AUDIT]\n")

    # Showcase of filtered noise
    noise_where = " WHERE tr.escalate = 0"
    noise_params = []
    if chat_id:
        noise_where += " AND t.chat_id = ?"
        noise_params.append(chat_id)

    cur.execute(f"""
    SELECT t.thread_id, t.start_date, t.message_count, tr.salience_score, tr.primary_category,
           substr(t.dialogue_text, 1, 100)
    FROM thread_triage tr
    JOIN threads t ON tr.thread_id = t.thread_id
    {noise_where}
    ORDER BY tr.salience_score ASC
    LIMIT 3
    """, tuple(noise_params))
    noise_samples = cur.fetchall()

    if noise_samples:
        print("🗑️ FILTERED NOISE SAMPLES (Correctly pruned without burning LLM tokens):")
        print("-" * 80)
        for nid, ndate, nmsgs, nscore, ncat, ntext in noise_samples:
            print(f"[{ndate}] Thread {nid} | Msgs: {nmsgs} | Cat: {ncat} | Score: {nscore:.1f}")
            teaser = ntext.strip().replace(chr(10), " ")[:70]
            print(f"  Sample:  \"{teaser}...\"\n")
    print("=" * 80)
