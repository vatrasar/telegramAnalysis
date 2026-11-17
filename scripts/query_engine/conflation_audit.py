"""Immediate anti-conflation and collision risk audit for registered entities."""

import re
import sqlite3
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
    "it_dev": ["developer", "programista", "it", "software", "inżynier"]
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


GENERIC_IGNORE_TOKENS = {"the", "and", "suitor", "friend", "person", "candidate", "someone"}


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
    """Tokenize text into lowercase alphanumeric words (min 3 chars), excluding participant/noise tokens."""
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
    """Run immediate anti-conflation and collision risk audit on registered entities."""
    entities = get_chat_entities(db_path, chat_id=chat_id)
    if len(entities) < 2:
        return {
            "chat_id": chat_id,
            "total_entities": len(entities),
            "collision_pairs": [],
            "status": "clear",
            "message": "Fewer than 2 entities registered. No collision risk possible yet."
        }

    # Load dynamic participant tokens to prevent self-collision
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

            t1_name = _extract_tokens(e1["name_or_alias"], exclude_tokens)
            t2_name = _extract_tokens(e2["name_or_alias"], exclude_tokens)
            shared_name_tokens = t1_name.intersection(t2_name)

            # Restrict role checking to name and verified_role (plus short descriptor), not full background notes
            role_text1 = f"{e1['name_or_alias']} {e1['verified_role'] or ''}".lower()
            role_text2 = f"{e2['name_or_alias']} {e2['verified_role'] or ''}".lower()

            shared_roles = []
            for role_group, kws in ROLE_KEYWORDS.items():
                if _matches_keyword(role_text1, kws) and _matches_keyword(role_text2, kws):
                    shared_roles.append(role_group)

            demo_text1 = f"{e1['name_or_alias']} {e1['verified_role'] or ''} {e1['associated_descriptors'] or ''}".lower()
            demo_text2 = f"{e2['name_or_alias']} {e2['verified_role'] or ''} {e2['associated_descriptors'] or ''}".lower()

            shared_demographics = []
            for demo_group, kws in DEMOGRAPHIC_KEYWORDS.items():
                if _matches_keyword(demo_text1, kws) and _matches_keyword(demo_text2, kws):
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
                    "risk_level": risk_level,
                    "status": "GUARDED" if is_fully_guarded else "UNRESOLVED_CONFLATION_RISK"
                })

    high_risk_count = sum(1 for p in collision_pairs if p["risk_level"] == "HIGH_RISK")
    overall_status = "WARNING_CONFLATION_DETECTED" if high_risk_count > 0 else "OK"

    return {
        "chat_id": chat_id,
        "total_entities": len(entities),
        "total_potential_collisions": len(collision_pairs),
        "high_risk_unresolved": high_risk_count,
        "status": overall_status,
        "collision_pairs": collision_pairs
    }


def print_conflation_audit(report: Dict[str, Any]) -> None:
    """Print ASCII report of anti-conflation audit."""
    print("\n" + "=" * 80)
    print(f"🚨 IMMEDIATE ANTI-CONFLATION & COLLISION AUDIT [Chat: {report.get('chat_id', '')}]")
    print(f"   Registered Entities Scanned:  {report.get('total_entities', 0)}")
    print(f"   Potential Collision Pairs:    {report.get('total_potential_collisions', 0)}")
    print(f"   High Risk Unresolved:         {report.get('high_risk_unresolved', 0)}")
    print("=" * 80)

    pairs = report.get("collision_pairs", [])
    if not pairs:
        print("✓ No character collisions detected. All registered entities have distinct names, roles, and traits.")
        print("=" * 80 + "\n")
        return

    for idx, p in enumerate(pairs, 1):
        e1 = p["entity_1"]
        e2 = p["entity_2"]
        badge = "🛡️  GUARDED" if p["risk_level"] == "GUARDED" else "🚨 HIGH RISK (UNRESOLVED)"
        print(f"\n[{idx}] {badge}")
        print(f"   Entity 1: '{e1['name']}' (Role: {e1['role'] or 'unspecified'})")
        print(f"             Negative Boundary: {'[✓ DEFINED]' if e1['has_negative_boundary'] else '[❌ MISSING]'}")
        print(f"   Entity 2: '{e2['name']}' (Role: {e2['role'] or 'unspecified'})")
        print(f"             Negative Boundary: {'[✓ DEFINED]' if e2['has_negative_boundary'] else '[❌ MISSING]'}")
        print(f"   Collision Factor: {'; '.join(p['reasons'])}")

        if p["risk_level"] == "HIGH_RISK":
            print("   👉 CONSOLIDATED DISAMBIGUATION ACTIONS:")
            print("      1. Trace evidence threads: confirm whether these are 2 distinct people or 1 person under aliases.")
            print("      2. Disambiguate attributes: map which facts and timeline milestones belong strictly to which entity.")
            print("      3. ⚠️ Flag ambiguous traits: if an event/quote cannot be definitively assigned, explicitly mark it")
            print("         as '[AMBIGUOUS ATTRIBUTION]' rather than guessing or force-assigning.")
            print("      4. Inject explicit negative boundaries in descriptors:")
            print(f"         python3 project/scripts/query_chat.py -C {report.get('chat_id')} \\")
            print(f"           --register-entity \"{e1['name']}\" --desc \"{e1['descriptors'] or '...'} (NOT {e2['name']})\"")

    print("\n" + "=" * 80 + "\n")
