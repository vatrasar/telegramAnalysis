"""
Domain Fact Packets & Specialized Decider Routing Engine (Track B).

Partitions the established facts baseline into targeted, domain-specific packets
(max 200 facts per chunk) with customized decider instructions for each life sphere.
Prevents cognitive overload and attention degradation in System-1 models.
"""

import re
import json
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

DOMAIN_SPECS = {
    "family": {
        "name": "Rodzina i Wychowanie",
        "description": "Family dynamics, parental authority, sibling relationships, filial pressure, and childhood imprints.",
        "instructions": (
            "Evaluate strictly whether this dialogue introduces ANY NOVEL, UNRECORDED FACTS regarding "
            "family dynamics, parents (father, mother), siblings, domestic upbringing, or filial marriage pressure "
            "that are NOT already documented in the Family baseline."
        ),
        "target_category": "corroborating_family_conflict",
        "keywords": ["father", "mother", "sister", "brother", "parents", "aunt", "uncle", "arranged", "family", "filial"]
    },
    "romantic": {
        "name": "Relacje Romantyczne i Byli Partnerzy",
        "description": "Romantic history, suitors, ex-partners (Caleb, Hilal), courtship filtering, and marriage expectations.",
        "instructions": (
            "Evaluate strictly whether this dialogue introduces ANY NOVEL, UNRECORDED FACTS regarding "
            "romantic relationships, dating apps, prospective suitors, ex-partners (Caleb/CJ, Hilal), "
            "breakup aftermath, or premarital vetting criteria that are NOT already documented in the Romantic baseline."
        ),
        "target_category": "corroborating_courtship_filtering",
        "keywords": ["caleb", "cj", "hilal", "ex", "suitor", "dating", "app", "courtship", "marry", "marriage", "breakup", "matchmaking"]
    },
    "health_psychodynamics": {
        "name": "Zdrowie, Psychodynamika i Traumy",
        "description": "Physical/mental health, surgeries, illness, panic attacks, emotional decompensation, and defense mechanisms.",
        "instructions": (
            "Evaluate strictly whether this dialogue introduces ANY NOVEL, UNRECORDED FACTS regarding "
            "physical/somatic illness, surgeries, hospitalizations, emotional breakdowns, panic, "
            "compulsive protest behavior, or psychological defense mechanisms that are NOT already documented in the Health baseline."
        ),
        "target_category": "corroborating_health_somatic",
        "keywords": ["tumor", "fibroadenoma", "surgery", "hospital", "painkiller", "epilepsy", "crying", "breakdown", "burnout", "panic", "suicide", "relapse", "hyperglycemia"]
    },
    "career_values": {
        "name": "Kariera, Studia i Wartości",
        "description": "Medical studies/thesis, clinical shifts, career aspirations, financial management, religious boundaries, and worldview.",
        "instructions": (
            "Evaluate strictly whether this dialogue introduces ANY NOVEL, UNRECORDED FACTS regarding "
            "vocational trajectory, medical school exams/internship, clinical work, finances, "
            "Islamic religious boundaries (halal/haram), or cultural/political philosophy that are NOT already documented in the Career/Values baseline."
        ),
        "target_category": "corroborating_academic_anxiety",
        "keywords": ["study", "medical", "doctor", "clinic", "shift", "exam", "thesis", "career", "money", "finance", "religion", "islam", "convert", "halal", "haram", "politics"]
    }
}


def _classify_fact_to_domain(category: str, sphere_id: str) -> str:
    """Classify a single fact into one of the 4 core domains."""
    cat = (category or "").lower()
    sid = (sphere_id or "").upper()

    if "fam" in cat or "parent" in cat or sid == "A":
        return "family"
    if "romant" in cat or "court" in cat or "relat" in cat or sid == "B":
        return "romantic"
    if "med" in cat or "health" in cat or "attach" in cat or "psycho" in cat or "trigger" in cat or sid in ("D", "E"):
        return "health_psychodynamics"
    if "career" in cat or "academ" in cat or "politic" in cat or "socio" in cat or "cultur" in cat or "creativ" in cat or sid in ("C", "F"):
        return "career_values"

    # Default fallback to family/roots if ambiguous
    return "family"


def build_fact_packets(
    conn: sqlite3.Connection,
    chat_id: str,
    max_per_chunk: int = 200
) -> List[Dict[str, Any]]:
    """
    Build partitioned domain fact packets from discovered_facts and life_spheres_checklist.
    Ensures that no packet chunk exceeds max_per_chunk (default: 200 facts).
    """
    cur = conn.cursor()
    cur.execute("""
    SELECT fact_id, category, coalesce(sphere_id, ''), fact_summary
    FROM discovered_facts
    WHERE chat_id = ?
    ORDER BY fact_id ASC;
    """, (chat_id,))
    rows = cur.fetchall()

    domain_buckets: Dict[str, List[str]] = {
        "family": [],
        "romantic": [],
        "health_psychodynamics": [],
        "career_values": []
    }

    for fact_id, cat, sid, summary in rows:
        dom = _classify_fact_to_domain(cat, sid)
        clean_sum = summary.strip().replace("\n", " ")
        domain_buckets[dom].append(f"[#{fact_id} | {cat}] {clean_sum}")

    # Supplement domains with low fact counts from life_spheres_checklist
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='life_spheres_checklist';")
    if cur.fetchone()[0] > 0:
        cur.execute("""
        SELECT sphere_id, category, evidence_summary
        FROM life_spheres_checklist
        WHERE chat_id = ? AND status = 'completed' AND evidence_summary IS NOT NULL;
        """, (chat_id,))
        for sid, cat, evidence in cur.fetchall():
            dom = _classify_fact_to_domain(cat, sid)
            clean_ev = evidence.strip().replace("\n", " ")[:150]
            domain_buckets[dom].append(f"[Sphere {sid} | {cat}] {clean_ev}")

    # Chunk each domain into packets of max_per_chunk
    packets: List[Dict[str, Any]] = []
    for dom_key, spec in DOMAIN_SPECS.items():
        facts_list = domain_buckets.get(dom_key, [])
        if not facts_list:
            continue

        total_facts = len(facts_list)
        chunks = [facts_list[i:i + max_per_chunk] for i in range(0, total_facts, max_per_chunk)]

        for idx, chunk in enumerate(chunks, 1):
            chunk_suffix = f" (Part {idx})" if len(chunks) > 1 else ""
            packet_id = f"{dom_key}_p{idx}" if len(chunks) > 1 else dom_key
            packet_text = "\n".join(f"- {f}" for f in chunk)

            packets.append({
                "packet_id": packet_id,
                "domain": dom_key,
                "name": f"{spec['name']}{chunk_suffix}",
                "total_facts": len(chunk),
                "instructions": spec["instructions"],
                "target_category": spec["target_category"],
                "keywords": spec["keywords"],
                "baseline_text": packet_text
            })

    return packets


def map_thread_to_domain(
    primary_category: str,
    summary_text: str,
    radar_sources: str
) -> str:
    """Determine the primary domain packet to evaluate a thread against."""
    cat = (primary_category or "").lower()
    sum_lower = (summary_text or "").lower()
    radar = (radar_sources or "").lower()

    # Keyword overrides based on high-specificity domain indicators
    if any(k in sum_lower for k in ["caleb", "cj", "hilal", "suitor", "dating", "courtship", "ex-partner"]):
        return "romantic"
    if any(k in sum_lower for k in ["father", "mother", "sister", "brother", "parents", "arranged marriage"]):
        return "family"
    if any(k in sum_lower for k in ["tumor", "surgery", "hospital", "epilepsy", "painkiller", "breakdown", "crying"]):
        return "health_psychodynamics"
    if any(k in sum_lower for k in ["study", "medical school", "thesis", "clinic", "shift", "exam"]):
        return "career_values"

    # Category mappings
    if cat in ["family", "parental_imprints"]:
        return "family"
    if cat in ["romantic", "courtship", "intimacy"]:
        return "romantic"
    if cat in ["health", "emotional_vulnerability", "trauma"]:
        return "health_psychodynamics"
    if cat in ["career", "work", "values_and_worldview", "trivial_logistics"]:
        return "career_values"

    return "family"


def evaluate_domain_novelty(
    row_dict: Dict[str, Any],
    packet: Dict[str, Any],
    all_domain_packets: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Evaluate whether a dialogue thread presents novel facts in the specified domain
    versus corroborating the domain packet's established baseline.
    When all_domain_packets is provided, echo discounting inspects all domain packets
    to prevent false positives from facts split across multiple packets.
    """
    summary = str(row_dict.get("summary_short") or "").lower()
    salience = float(row_dict.get("salience_score") or 2.0)
    is_crisis = int(row_dict.get("is_medical_or_grief_crisis") or 0)
    is_bdown = int(row_dict.get("is_acute_vulnerability_or_breakdown") or 0)
    is_bizarre = int(row_dict.get("is_bizarre_or_boundary_violation") or 0)
    is_rel = int(row_dict.get("is_relational_conflict") or 0)
    peak = str(row_dict.get("emotional_peak") or "none")
    radar = str(row_dict.get("radar_sources") or "")
    if all_domain_packets:
        base_lower = " \n ".join(p.get("baseline_text", "").lower() for p in all_domain_packets)
    else:
        base_lower = packet["baseline_text"].lower()
    domain = packet["domain"]

    # 1. Echo discounting: check if core events mentioned are already explicitly recorded in this packet
    is_echo = False
    if domain == "health_psychodynamics":
        if ("tumor" in summary or "fibroadenoma" in summary or "surgery" in summary or "painkiller" in summary) and \
           ("tumor" in base_lower or "fibroadenoma" in base_lower) and not (is_bdown or is_bizarre or is_rel):
            is_echo = True
    elif domain == "family":
        if ("doctor" in summary or "tulakan" in summary or "retired" in summary or "clinic" in summary) and \
           ("tulakan" in base_lower or "retired in march 2024" in base_lower) and not (is_bdown or is_crisis):
            # Known background fact about father's job
            if not any(k in summary for k in ["arranged", "suitor", "marry", "marriage", "pressure", "ultimatum"]):
                is_echo = True
    elif domain == "romantic":
        if ("caleb" in summary or "cj" in summary) and ("religious differences" in summary or "convert" in summary) and \
           ("declines to convert" in base_lower or "terminates relationship" in base_lower):
            if not any(k in summary for k in ["relapse", "calling", "instagram", "brother", "facebook", "suicide"]):
                is_echo = True

    if is_echo:
        return {
            "decision": "redundant",
            "novelty_score": 1.5,
            "corroborating_theme": packet["target_category"],
            "justification": f"Corroborates established baseline facts in {packet['name']}"
        }

    # 2. Domain-specific novelty detection
    novelty_points = 0.0
    matched_reasons = []

    if domain == "family":
        if any(k in summary for k in ["arranged", "suitor", "home visit", "ultimatum", "aunt", "uncle", "age 30", "must marry", "hair regrowth", "secretly"]):
            novelty_points += 2.5
            matched_reasons.append("unrecorded paternal/extended kin marriage pressure")
        if any(k in summary for k in ["silent treatment", "frustration", "short replies", "last-minute", "scheduling"]):
            novelty_points += 1.8
            matched_reasons.append("specific paternal communication trigger")

    elif domain == "romantic":
        if any(k in summary for k in ["brother", "instagram", "photos", "audio recordings", "relapse", "suicide", "suicidal", "calling", "blocked"]):
            novelty_points += 2.8
            matched_reasons.append("acute post-breakup boundary violation / attachment relapse")
        if any(k in summary for k in ["gardening", "separate preferences", "domestic burden", "dating app", "20 question"]):
            novelty_points += 2.0
            matched_reasons.append("specific premarital mate selection creed / boundary")

    elif domain == "health_psychodynamics":
        if any(k in summary for k in ["epilepsy", "second sister", "hospitalized bfore", "panic", "burnout"]):
            novelty_points += 2.5
            matched_reasons.append("unmapped chronic medical / caregiver reality")
        if is_bdown or is_bizarre:
            novelty_points += 2.5
            matched_reasons.append("acute psychological breakdown or boundary decompensation")

    elif domain == "career_values":
        if any(k in summary for k in ["exam", "thesis", "burnout", "dropped", "us licensing", "abandon"]):
            novelty_points += 2.2
            matched_reasons.append("academic burnout / career milestone shift")
        if any(k in summary for k in ["convert", "halal", "haram", "islamic prohibition", "alcohol"]):
            novelty_points += 1.8
            matched_reasons.append("explicit moral/religious boundary negotiation")

    # Global crisis elevation
    if is_bdown:
        novelty_points += 2.0
    if is_crisis and not is_echo:
        novelty_points += 1.5
    if peak in ["profound_sadness", "intense_rage"] and not is_echo:
        novelty_points += 1.5

    calculated_score = min(5.0, 1.0 + novelty_points)

    if calculated_score >= 3.0 or salience >= 3.9:
        reason_str = ", ".join(matched_reasons) if matched_reasons else f"Domain novelty in {packet['name']}"
        return {
            "decision": "novel",
            "novelty_score": round(calculated_score, 1),
            "corroborating_theme": "novel_investigate",
            "justification": f"Domain Novelty ({packet['name']}, score {calculated_score:.1f}): {reason_str}"
        }

    return {
        "decision": "redundant",
        "novelty_score": round(calculated_score, 1),
        "corroborating_theme": packet["target_category"],
        "justification": f"Corroborates established baseline in {packet['name']} (score {calculated_score:.1f})"
    }


def verify_quote_in_packets(
    quote: str,
    other_packets: List[Dict[str, Any]],
    api_key: str,
    model: str
) -> Tuple[bool, float]:
    """Verify whether a candidate unrecorded quote is already documented in other fact packets."""
    clean_quote = (quote or "").strip()
    if len(clean_quote) < 8:
        return False, 0.0

    total_cost = 0.0
    for pkt in other_packets:
        base_text = pkt.get("baseline_text", "")
        if not base_text:
            continue
        state_payload = (
            f"ESTABLISHED BASELINE FACTS:\n{base_text}\n\n"
            f"QUOTE TO VERIFY:\n\"{clean_quote}\""
        )
        url = "https://openrouter.ai/api/alpha/decisions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
            "X-Title": "System-1 Cross-Packet Verifier"
        }
        payload = {
            "model": model,
            "state": state_payload,
            "questions": {
                "is_documented": {
                    "type": "noul",
                    "instructions": (
                        "Is the event, biographical milestone, relationship detail, or factual disclosure "
                        "in QUOTE TO VERIFY already documented, corroborated, or accounted for in ESTABLISHED BASELINE FACTS?"
                    )
                }
            }
        }
        req_data = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                prob = float(data.get("answers", {}).get("is_documented", {}).get("noul", 0.0))
                total_cost += float(data.get("usage", {}).get("cost", 0.0))
                if prob >= 0.5:
                    return True, total_cost
        except Exception:
            pass

    return False, total_cost

