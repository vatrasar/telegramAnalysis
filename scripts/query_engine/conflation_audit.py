"""Immediate anti-conflation and collision risk audit for registered entities with cluster grouping."""

import os
import re
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from .entities import get_chat_entities

# Critical kinship and social role keywords prone to conflation
ROLE_KEYWORDS = {
    "sister": ["sister", "siostra", "sis"],
    "brother": ["brother", "brat", "bro"],
    "mother": ["mother", "matka", "mama", "mom"],
    "father": ["father", "ojciec", "tata", "dad"],
    "ex": ["ex", "były", "była", "ex-partner", "ex-boyfriend", "ex-girlfriend", "ekspartner"],
    "boss": ["boss", "szef", "szefowa", "manager", "przełożony", "przełożona", "supervisor"],
    "doctor": ["doctor", "lekarz", "lekarka", "psychiatra", "terapeuta", "therapist", "psycholog", "dr"],
    "roommate": ["roommate", "współlokator", "współlokatorka", "flatmate"],
    "coworker": ["coworker", "kolega z pracy", "koleżanka z pracy", "colleague"],
    "suitor": ["suitor", "randka", "tinder", "badoo", "bumble", "date"]
}

# Salient demographic, geographic, or nationality descriptors
DEMOGRAPHIC_KEYWORDS = {
    "indian": ["indian", "hindus", "hinduska", "indie", "india"],
    "british": ["british", "brytyjczyk", "anglik", "uk", "london", "londyn"],
    "spanish": ["spanish", "hiszpan", "hiszpanka", "spain", "hiszpania"],
    "american": ["american", "amerykanin", "amerykanka", "usa", "us"],
    "german": ["german", "niemiec", "niemka", "germany"],
    "french": ["french", "francuz", "francuzka", "france"],
    "it_dev": ["developer", "programista", "software", "inżynier"]
}

NEGATIVE_BOUNDARY_PATTERNS = [
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bnie\b", re.IGNORECASE),
    re.compile(r"to\s+nie\b", re.IGNORECASE),
    re.compile(r"distinct\s+from", re.IGNORECASE),
    re.compile(r"different\s+than", re.IGNORECASE),
    re.compile(r"do\s+not\s+confuse", re.IGNORECASE),
    re.compile(r"odr[eę]bn[ay]", re.IGNORECASE)
]

# Multilingual generic stopwords, prepositions, and structural noise words
GENERIC_IGNORE_TOKENS = {
    "the", "and", "suitor", "friend", "person", "candidate", "someone",
    "from", "with", "for", "about", "into", "over", "under", "near",
    "across", "after", "before", "local", "online", "distant", "dist",
    "school", "marriage", "maternal", "paternal", "village", "city",
    "dla", "pod", "nad", "przy", "przez", "oraz", "albo", "jego", "jej", "ich",
    "dari", "pada", "yang", "untuk", "dengan", "dalam", "anak", "teman"
}


def _get_chat_participant_tokens(db_path: str, chat_id: str) -> Set[str]:
    """Fetch participant and chat name tokens to exclude from cross-entity collisions dynamically."""
    tokens = set(GENERIC_IGNORE_TOKENS)
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT chat_name FROM chats WHERE chat_id = ?", (chat_id,))
        r = cur.fetchone()
        if r and r[0]:
            for w in re.findall(r"\b[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}\b", r[0].lower()):
                tokens.add(w)
        cur.execute("SELECT DISTINCT sender FROM messages WHERE chat_id = ? LIMIT 20", (chat_id,))
        for (sender,) in cur.fetchall():
            if sender:
                for w in re.findall(r"\b[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}\b", sender.lower()):
                    tokens.add(w)
        conn.close()
    except Exception:
        pass
    return tokens


def _extract_tokens(text: str, exclude_tokens: Optional[Set[str]] = None) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words (min 3 chars), excluding noise tokens."""
    words = re.findall(r"\b[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}\b", text.lower())
    if exclude_tokens:
        return {w for w in words if w not in exclude_tokens}
    return set(words)


def _check_negative_boundary(
    e1: Dict[str, Any],
    e2: Dict[str, Any],
    verified_pairs: Optional[Set[Tuple[str, str]]] = None
) -> bool:
    """Check if entity e1 explicitly sets a negative boundary referencing e2 or is cached in disambiguation table."""
    name1 = e1.get("name_or_alias", "").lower()
    name2 = e2.get("name_or_alias", "").lower()
    pair = tuple(sorted([name1, name2]))
    if verified_pairs and pair in verified_pairs:
        return True

    notes1 = (e1.get("associated_descriptors", "") + " " + e1.get("notes", "")).lower()
    e2_name = e2.get("name_or_alias", "").lower()
    e2_id = e2.get("entity_id", "").lower()

    mentions_other = (e2_name in notes1) or (e2_id in notes1)
    has_neg_pattern = any(p.search(notes1) for p in NEGATIVE_BOUNDARY_PATTERNS)
    return mentions_other and has_neg_pattern


def _matches_keyword(text: str, kws: List[str]) -> bool:
    """Check if any keyword matches as a whole word in text."""
    for kw in kws:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            return True
    return False


def run_conflation_audit(db_path: str, chat_id: str) -> Dict[str, Any]:
    """Run anti-conflation and collision risk audit on registered entities with cluster grouping."""
    entities = get_chat_entities(db_path, chat_id=chat_id)
    if len(entities) < 2:
        return {
            "chat_id": chat_id,
            "total_entities": len(entities),
            "collision_pairs": [],
            "clusters": [],
            "status": "clear",
            "message": "Fewer than 2 entities registered. No collision risk possible yet."
        }

    exclude_tokens = _get_chat_participant_tokens(db_path, chat_id)

    # Load verified distinct pairs from SQLite
    verified_pairs: Set[Tuple[str, str]] = set()
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT entity_a, entity_b FROM entity_disambiguation_pairs WHERE chat_id = ? AND status = 'verified_distinct';",
            (chat_id,)
        )
        for r in cur.fetchall():
            verified_pairs.add(tuple(sorted([r[0].lower(), r[1].lower()])))
        conn.close()
    except Exception:
        pass

    collision_pairs: List[Dict[str, Any]] = []

    for i in range(len(entities)):
        for j in range(i + 1, len(entities)):
            e1 = entities[i]
            e2 = entities[j]

            n1_low = e1["name_or_alias"].lower()
            n2_low = e2["name_or_alias"].lower()

            # Separate interlocutor kinship from subject kinship
            is_szymon_1 = "szymon's" in n1_low or "szymona" in n1_low
            is_szymon_2 = "szymon's" in n2_low or "szymona" in n2_low
            is_subject_1 = ("ismi's" in n1_low or "ismi" in n1_low) and not is_szymon_1
            is_subject_2 = ("ismi's" in n2_low or "ismi" in n2_low) and not is_szymon_2
            if (is_szymon_1 and is_subject_2) or (is_szymon_2 and is_subject_1):
                continue

            t1_name = _extract_tokens(e1["name_or_alias"], exclude_tokens)
            t2_name = _extract_tokens(e2["name_or_alias"], exclude_tokens)
            shared_name_tokens = t1_name.intersection(t2_name)

            # Match roles strictly on name + verified_role (not descriptors with boundary texts)
            role_text1 = f"{e1['name_or_alias']} {e1['verified_role'] or ''}".lower()
            role_text2 = f"{e2['name_or_alias']} {e2['verified_role'] or ''}".lower()

            shared_roles = []
            for role_group, kws in ROLE_KEYWORDS.items():
                if _matches_keyword(role_text1, kws) and _matches_keyword(role_text2, kws):
                    shared_roles.append(role_group)

            # Match demographics on name + verified_role
            shared_demographics = []
            for demo_group, kws in DEMOGRAPHIC_KEYWORDS.items():
                if _matches_keyword(role_text1, kws) and _matches_keyword(role_text2, kws):
                    shared_demographics.append(demo_group)

            reasons = []
            if shared_name_tokens:
                reasons.append(f"Shared name token(s): [{', '.join(sorted(shared_name_tokens))}]")
            if shared_roles:
                reasons.append(f"Shared role category: [{', '.join(sorted(shared_roles))}]")
            if shared_demographics:
                reasons.append(f"Shared demographic/trait: [{', '.join(sorted(shared_demographics))}]")

            if reasons:
                e1_guarded = _check_negative_boundary(e1, e2, verified_pairs)
                e2_guarded = _check_negative_boundary(e2, e1, verified_pairs)
                pair_key = tuple(sorted([e1['name_or_alias'].lower(), e2['name_or_alias'].lower()]))
                is_fully_guarded = e1_guarded or e2_guarded or (pair_key in verified_pairs)

                risk_level = "GUARDED" if is_fully_guarded else "HIGH_RISK"

                collision_pairs.append({
                    "entity_1": {
                        "id": e1["entity_id"],
                        "name": e1["name_or_alias"],
                        "role": e1["verified_role"],
                        "descriptors": e1["associated_descriptors"],
                        "has_negative_boundary": e1_guarded
                    },
                    "entity_2": {
                        "id": e2["entity_id"],
                        "name": e2["name_or_alias"],
                        "role": e2["verified_role"],
                        "descriptors": e2["associated_descriptors"],
                        "has_negative_boundary": e2_guarded
                    },
                    "reasons": reasons,
                    "shared_roles": shared_roles,
                    "risk_level": risk_level,
                    "status": "GUARDED" if is_fully_guarded else "UNRESOLVED_CONFLATION_RISK"
                })

    # Group unresolved collision pairs into coherent thematic clusters
    cluster_buckets: Dict[str, Set[str]] = {}
    cluster_pairs: Dict[str, List[Dict[str, Any]]] = {}

    unresolved_pairs = [p for p in collision_pairs if p["risk_level"] == "HIGH_RISK"]
    for p in unresolved_pairs:
        sroles = p.get("shared_roles", [])
        if sroles:
            cgroup = sroles[0]
        else:
            cgroup = "other"

        if cgroup not in cluster_buckets:
            cluster_buckets[cgroup] = set()
            cluster_pairs[cgroup] = []

        cluster_buckets[cgroup].add(p["entity_1"]["name"])
        cluster_buckets[cgroup].add(p["entity_2"]["name"])
        cluster_pairs[cgroup].append(p)

    clusters_report = []
    clustered_pair_count = 0
    for cgroup, members in sorted(cluster_buckets.items(), key=lambda x: -len(x[1])):
        if len(members) >= 2:
            cp_list = cluster_pairs[cgroup]
            clustered_pair_count += len(cp_list)
            clusters_report.append({
                "cluster_id": cgroup,
                "title": cgroup.capitalize(),
                "member_count": len(members),
                "members": sorted(list(members)),
                "unresolved_pair_count": len(cp_list),
                "pairs": cp_list
            })

    high_risk_count = len(unresolved_pairs)
    overall_status = "WARNING_CONFLATION_DETECTED" if high_risk_count > 0 else "OK"

    return {
        "chat_id": chat_id,
        "total_entities": len(entities),
        "total_potential_collisions": len(collision_pairs),
        "high_risk_unresolved": high_risk_count,
        "clusters_count": len(clusters_report),
        "clusters": clusters_report,
        "status": overall_status,
        "collision_pairs": collision_pairs
    }


def print_conflation_audit(report: Dict[str, Any]) -> None:
    """Print ASCII report of anti-conflation audit organized into thematic clusters."""
    chat_id = report.get("chat_id", "")
    print("\n" + "=" * 80)
    print(f"🚨 IMMEDIATE ANTI-CONFLATION & COLLISION AUDIT [Chat: {chat_id}]")
    print(f"   Registered Entities Scanned:  {report.get('total_entities', 0)}")
    print(f"   Potential Collision Pairs:    {report.get('total_potential_collisions', 0)}")
    print(f"   High Risk Unresolved:         {report.get('high_risk_unresolved', 0)}")
    print(f"   Unresolved Thematic Clusters: {report.get('clusters_count', 0)}")
    print("=" * 80)

    clusters = report.get("clusters", [])
    all_pairs = report.get("collision_pairs", [])
    guarded_count = sum(1 for p in all_pairs if p["risk_level"] == "GUARDED")

    if report.get("high_risk_unresolved", 0) == 0:
        print("✓ All registered entities verified. No unresolved conflation risks detected.")
        if guarded_count > 0:
            print(f"🛡️  {guarded_count} pairwise relations verified & guarded in SQLite (entity_disambiguation_pairs).")
        print("=" * 80 + "\n")
        return

    # 1. Print thematic clusters
    if clusters:
        print("\n👥 THEMATIC CONFLATION CLUSTERS (AUDIT TOGETHER AS A COHORT):")
        print("   Do not split into individual pairwise reviews. Delegate each cluster to an entity-investigator subagent.\n")

        for idx, cl in enumerate(clusters, 1):
            cid = cl["cluster_id"]
            cnt = cl["member_count"]
            pr_cnt = cl["unresolved_pair_count"]
            print(f"[{idx}] CLUSTER: '{cl['title']}' ({cnt} members | {pr_cnt} pairwise collisions)")
            print("   Members in Cohort:")
            for m in cl["members"]:
                print(f"     • {m}")

            print("   👉 SUBAGENT INVESTIGATION MANDATE:")
            print(f"      1. Dispatch an entity-investigator subagent to audit this entire {cnt}-member cohort.")
            print("      2. If any members are duplicate aliases of the same person, merge them:")
            print(f"         python3 project/scripts/query_chat.py -C {chat_id} --merge-entity <src> --into-entity <tgt> --reason '<evidence>'")
            print("      3. If all members in this cohort are verified distinct individuals, resolve the entire cluster at once:")
            print(f"         python3 project/scripts/query_chat.py -C {chat_id} --resolve-cluster \"{cid}\" --reason '<investigation notes & distinct anchors>'")
            print("-" * 80)

    # 2. Print any individual isolated pairs (outside of defined role clusters)
    isolated_pairs = [
        p for p in all_pairs
        if p["risk_level"] == "HIGH_RISK" and (not p.get("shared_roles") or p.get("shared_roles")[0] == "other")
    ]
    if isolated_pairs:
        print(f"\n⚠️  ISOLATED COLLISION PAIRS ({len(isolated_pairs)} pairs):")
        for idx, p in enumerate(isolated_pairs, 1):
            e1 = p["entity_1"]
            e2 = p["entity_2"]
            print(f"  [{idx}] '{e1['name']}' vs '{e2['name']}'")
            print(f"      Factor: {'; '.join(p['reasons'])}")
            print(f"      Action: python3 project/scripts/query_chat.py -C {chat_id} --record-distinct-pair \"{e1['name']}\" \"{e2['name']}\" --reason '<evidence>'")

    if guarded_count > 0:
        print(f"\n🛡️  {guarded_count} other collision pairs are already GUARDED in SQLite.")

    print("\n" + "=" * 80 + "\n")


def resolve_entity_cluster(
    db_path: str,
    chat_id: str,
    cluster_key: str,
    reason: str
) -> Dict[str, Any]:
    """Resolve all pairwise collisions in a named cluster in a single atomic SQLite transaction."""
    if not reason or not reason.strip():
        return {"error": "Resolving a cluster requires an explicit --reason '<audit findings & anchors>'."}

    entities = get_chat_entities(db_path, chat_id=chat_id)
    ck = cluster_key.strip().lower()

    # Find matching entities by role keyword or substring in name / role
    kws = ROLE_KEYWORDS.get(ck, [ck])
    matched_entities = []
    for e in entities:
        text = f"{e['name_or_alias']} {e['verified_role'] or ''}".lower()
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE) for kw in kws) or ck in text:
            matched_entities.append(e)

    if len(matched_entities) < 2:
        return {
            "error": f"Found fewer than 2 entities matching cluster '{cluster_key}'. Matching: {[e['name_or_alias'] for e in matched_entities]}"
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    reason_clean = reason.strip()

    records = []
    names = [e["name_or_alias"] for e in matched_entities]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p1, p2 = sorted([names[i], names[j]])
            records.append((chat_id, p1, p2, now_iso, reason_clean, now_iso, reason_clean))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany("""
    INSERT INTO entity_disambiguation_pairs (chat_id, entity_a, entity_b, status, audited_at, reason)
    VALUES (?, ?, ?, 'verified_distinct', ?, ?)
    ON CONFLICT(chat_id, entity_a, entity_b) DO UPDATE SET
        status = 'verified_distinct', audited_at = ?, reason = ?;
    """, records)

    # Append single clean cluster note to matching entities
    cluster_tag = f"Cohort verified distinct ({cluster_key}): {reason_clean}"
    for e in matched_entities:
        eid = e["entity_id"]
        cur.execute("SELECT notes FROM chat_entities WHERE entity_id = ? AND chat_id = ?;", (eid, chat_id))
        r = cur.fetchone()
        old_notes = r[0] if r and r[0] else ""
        if cluster_tag not in old_notes:
            new_notes = f"{old_notes}; {cluster_tag}" if old_notes else cluster_tag
            cur.execute("UPDATE chat_entities SET notes = ?, updated_at = ? WHERE entity_id = ? AND chat_id = ?;",
                        (new_notes, now_iso, eid, chat_id))

    conn.commit()
    conn.close()

    return {
        "status": "cluster_resolved",
        "chat_id": chat_id,
        "cluster": cluster_key,
        "entities_count": len(matched_entities),
        "entities": names,
        "pairs_recorded": len(records),
        "reason": reason_clean
    }


def resolve_distinct_pairs_batch(
    db_path: str,
    chat_id: str,
    batch_input: str
) -> Dict[str, Any]:
    """Batch record verified distinct entity pairs from a JSON file or JSON string."""
    if os.path.isfile(batch_input):
        with open(batch_input, "r", encoding="utf-8") as f:
            pairs_data = json.load(f)
    else:
        pairs_data = json.loads(batch_input)

    if not isinstance(pairs_data, list):
        return {"error": "Batch input must be a JSON array of objects with 'entity_1', 'entity_2', and 'reason'."}

    now_iso = datetime.now(timezone.utc).isoformat()
    records = []
    for it in pairs_data:
        e1 = it.get("entity_1") or it.get("entity_a")
        e2 = it.get("entity_2") or it.get("entity_b")
        reason = it.get("reason", "").strip()
        if not e1 or not e2 or not reason:
            continue
        p1, p2 = sorted([e1, e2])
        records.append((chat_id, p1, p2, now_iso, reason, now_iso, reason))

    if not records:
        return {"error": "No valid pairs found in batch input."}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany("""
    INSERT INTO entity_disambiguation_pairs (chat_id, entity_a, entity_b, status, audited_at, reason)
    VALUES (?, ?, ?, 'verified_distinct', ?, ?)
    ON CONFLICT(chat_id, entity_a, entity_b) DO UPDATE SET
        status = 'verified_distinct', audited_at = ?, reason = ?;
    """, records)
    conn.commit()
    conn.close()

    return {
        "status": "batch_pairs_recorded",
        "chat_id": chat_id,
        "total_pairs_recorded": len(records)
    }
