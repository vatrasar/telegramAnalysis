"""Multi-label life sphere questions and answer parsing for System-1 triage."""

import json
from typing import Dict, Any, List


SPHERE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "A": {
        "name": "sphere_a_social",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding friendships, "
            "social circle, meeting friends, loyalty vs doorslamming, envy, or altruism?"
        )
    },
    "B": {
        "name": "sphere_b_career_money",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding work ethic, "
            "career ambitions, unfulfilled dreams, attitude to money, frugality vs lavishness, or budgeting?"
        )
    },
    "C": {
        "name": "sphere_c_worldview_tech",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding politics, "
            "ideology, ethics/tolerance, racism/discrimination, tech/AI posture, or socio-economic order?"
        )
    },
    "D": {
        "name": "sphere_d_family_domestic",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding parents, "
            "childhood imprints, siblings, apartment cleanliness, or domestic environment?"
        )
    },
    "E": {
        "name": "sphere_e_romantic",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding romantic partners, "
            "exes, dating etiquette/norms, intimacy avoidance, push-pull dynamics, or relationship conflicts?"
        )
    },
    "F": {
        "name": "sphere_f_leisure_lifestyle",
        "instructions": (
            "Does this thread contain substantive behavioral evidence regarding hobbies, "
            "sports, gym/exercise, travel, vacations, pets/animals, or distinct lifestyle quirks?"
        )
    }
}


def build_sphere_questions() -> Dict[str, Any]:
    """Generate discrete binary noul questions for multi-label sphere classification + locate quote."""
    questions: Dict[str, Any] = {}
    for _, meta in SPHERE_DEFINITIONS.items():
        questions[meta["name"]] = {
            "type": "noul",
            "instructions": meta["instructions"]
        }
    questions["key_evidence_quote"] = {
        "type": "locate",
        "instructions": (
            "Locate the exact verbatim sentence representing the peak personal disclosure, "
            "confession, core habit, or conflict in this dialogue."
        )
    }
    return questions


def parse_sphere_answers(answers: Dict[str, Any], threshold: float = 0.60) -> Dict[str, Any]:
    """Parse Decisions API answers for spheres and extract quote."""
    scores: Dict[str, float] = {}
    covered: List[str] = []

    for letter, meta in SPHERE_DEFINITIONS.items():
        q_name = meta["name"]
        ans = answers.get(q_name, {})
        val = float(ans.get("noul", ans.get("probability", 0.0)))
        scores[letter] = round(val, 3)
        if val >= threshold:
            covered.append(letter)

    covered.sort()
    covered_str = ",".join(covered)

    quote_data = answers.get("key_evidence_quote", {})
    evidence_quote = quote_data.get("span") or quote_data.get("text") or quote_data.get("verbatim") or ""
    span_start = quote_data.get("start_char", quote_data.get("start", None))
    span_end = quote_data.get("end_char", quote_data.get("end", None))

    return {
        "covered_spheres": covered_str,
        "sphere_scores": json.dumps(scores),
        "evidence_quote": str(evidence_quote).strip() if evidence_quote else "",
        "evidence_span_start": int(span_start) if span_start is not None else None,
        "evidence_span_end": int(span_end) if span_end is not None else None
    }
