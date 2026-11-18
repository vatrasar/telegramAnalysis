"""System-1 Automated Epistemic Invariants Auditor via OpenRouter Decisions API.

Evaluates synthesized psychological report sections against core constitutional rules:
1. Actuation Gate (Rule 1.3 / Modality & Irrealis vs Realis)
2. Medical, Somatic & Diagnostic Grounding Gate (Rule 1.4)
3. Thesis-Evidence Verbatim Fit & Anti-Eureka Standard (Rule 1.6 & 1.8)
4. Third-Party Entity Boundary & Trait Isolation (Rule 1.5)
"""

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

from common.config import load_config, get_api_key
from .parser import ParsedSection


@dataclass
class SectionAuditResult:
    """Audit evaluation result for a single section or subsection."""
    section_title: str
    source_file: Optional[str]
    passed: bool
    verdict: str
    breaches: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0


@dataclass
class EpistemicAuditReport:
    """Aggregated epistemic audit report for stitched chapters or subsections."""
    total_sections: int
    passed_sections: int
    failed_sections: int
    total_breaches: int
    total_warnings: int
    total_cost_usd: float
    results: List[SectionAuditResult] = field(default_factory=list)


def build_epistemic_questions() -> Dict[str, Any]:
    """Define the discrete question schema for OpenRouter Decisions API."""
    return {
        "irrealis_violation": {
            "type": "noul",
            "instructions": (
                "Actuation & Irrealis Gate: Does this psychological section assert as an accomplished, "
                "completed biographical fact, career milestone, or ongoing profession something that was in "
                "reality merely an unexecuted desire, aspiration, fantasy, plan, or offer "
                "(e.g., treating 'wanted to work at X' or 'thinking of moving' as completed realis facts)?"
            )
        },
        "psychiatric_hyperbole": {
            "type": "noul",
            "instructions": (
                "Diagnostic Grounding Gate: Does this text attribute a formal psychiatric diagnosis or severe "
                "chronic clinical condition (e.g., BPD, bipolar disorder, ADHD, clinical depression, epilepsy) "
                "to the subject as a definitive factual diagnosis without explicit, direct first-person medical "
                "self-disclosure of professional diagnosis, prescription, or clinical treatment?"
            )
        },
        "thesis_evidence_fit": {
            "type": "noul",
            "instructions": (
                "Thesis-Evidence Grounding: Do the cited verbatim quotes directly, logically, and credibly "
                "substantiate the specific psychological thesis asserted in this section?"
            )
        },
        "third_party_trait_leakage": {
            "type": "noul",
            "instructions": (
                "Entity Boundary & Trait Isolation: Does this section erroneously attribute traits, addictions, "
                "occupations, or traumas belonging to external third parties (e.g. parents, partners, interlocutor, "
                "or suitors) to the primary subject?"
            )
        },
        "overall_epistemic_rating": {
            "type": "choice",
            "instructions": "Rate the overall epistemic integrity and empirical grounding of this section:",
            "criteria": {
                "fully_grounded": "Strictly complies with epistemic invariants, factual grounding, and verbatim evidence",
                "minor_concerns": "Minor overreach or borderline speculation, but overall defensible",
                "epistemic_breach": "Significant epistemic violation: unactuated claims, casual psychiatric labeling, trait leakage, or unsupported claims"
            }
        }
    }


def call_decisions_api(
    state_payload: str,
    api_key: str,
    model: str,
    max_retries: int = 3
) -> Tuple[Dict[str, Any], float]:
    """Execute OpenRouter Decisions API request with retries."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "System-1 Epistemic Invariants Auditor"
    }

    payload = {
        "model": model,
        "state": state_payload,
        "questions": build_epistemic_questions()
    }
    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cost = float(data.get("usage", {}).get("cost", 0.0))
                return data.get("answers", {}), cost
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API HTTP {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.0 + attempt * 0.5)
                continue
            raise e

    raise RuntimeError(f"Decisions API failed after {max_retries} attempts.")


def audit_parsed_section(
    section: ParsedSection,
    api_key: str,
    model: str,
    threshold: float = 0.5
) -> SectionAuditResult:
    """Audit a single parsed section against epistemic invariants."""
    # Build compact state text
    state_parts = [
        f"SECTION TITLE: {section.title}",
        f"\nCORE THESIS:\n{section.thesis[:3500]}"
    ]
    if section.analysis:
        state_parts.append(f"\nPSYCHOLOGICAL ANALYSIS & CLAIMS:\n{section.analysis[:5000]}")
    if section.quotes:
        quotes_block = "\n".join(section.quotes[:15])
        state_parts.append(f"\nCITED VERBATIM EVIDENCE:\n{quotes_block[:4000]}")
    if section.takeaway:
        state_parts.append(f"\nKEY TAKEAWAY:\n{section.takeaway[:1000]}")

    state_text = "\n".join(state_parts)

    answers, cost = call_decisions_api(state_text, api_key, model)

    p_irrealis = float(answers.get("irrealis_violation", {}).get("noul", 0.0))
    p_psychiatric = float(answers.get("psychiatric_hyperbole", {}).get("noul", 0.0))
    p_fit = float(answers.get("thesis_evidence_fit", {}).get("noul", 1.0))
    p_leakage = float(answers.get("third_party_trait_leakage", {}).get("noul", 0.0))
    rating = str(answers.get("overall_epistemic_rating", {}).get("choice", "fully_grounded")).lower()

    breaches = []
    warnings = []

    if p_irrealis >= threshold:
        breaches.append(
            f"Actuation / Irrealis Violation (p={p_irrealis:.2f}): Claims may convert unexecuted desires/plans into completed biographical facts."
        )
    elif p_irrealis >= 0.35:
        warnings.append(f"Borderline Actuation Risk (p={p_irrealis:.2f}): Check if aspirational plans are framed as accomplishments.")

    if p_psychiatric >= threshold:
        breaches.append(
            f"Psychiatric Grounding Violation (p={p_psychiatric:.2f}): Clinical diagnosis or chronic condition attributed without explicit medical disclosure."
        )
    elif p_psychiatric >= 0.35:
        warnings.append(f"Borderline Psychiatric Labeling (p={p_psychiatric:.2f}): Verify direct medical disclosure grounding.")

    if p_fit < (1.0 - threshold):
        breaches.append(
            f"Thesis-Evidence Grounding Mismatch (p_fit={p_fit:.2f}): Quoted evidence does not adequately ground the asserted thesis."
        )
    elif p_fit < 0.65:
        warnings.append(f"Weak Evidence Fit (p_fit={p_fit:.2f}): Consider anchoring thesis with more direct verbatim citations.")

    if p_leakage >= threshold:
        breaches.append(
            f"Third-Party Trait Leakage (p={p_leakage:.2f}): Traits of parents, partners, or interlocutor may be misattributed to the subject."
        )
    elif p_leakage >= 0.35:
        warnings.append(f"Borderline Trait Leakage (p={p_leakage:.2f}): Check if third-party actions are isolated from subject's traits.")

    if rating == "epistemic_breach" and not breaches:
        breaches.append("Overall Epistemic Breach flagged by Decider evaluation.")

    passed = (len(breaches) == 0)

    return SectionAuditResult(
        section_title=section.title,
        source_file=section.source_file,
        passed=passed,
        verdict=rating,
        breaches=breaches,
        warnings=warnings,
        scores={
            "irrealis": round(p_irrealis, 3),
            "psychiatric": round(p_psychiatric, 3),
            "thesis_evidence_fit": round(p_fit, 3),
            "trait_leakage": round(p_leakage, 3)
        },
        cost_usd=cost
    )


def audit_sections_batch(
    sections: List[ParsedSection],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    threshold: float = 0.5,
    max_workers: int = 4
) -> EpistemicAuditReport:
    """Audit multiple parsed sections concurrently."""
    if not sections:
        return EpistemicAuditReport(0, 0, 0, 0, 0, 0.0, [])

    config = load_config()
    key = api_key or get_api_key(config)
    if not key:
        raise ValueError("Missing OpenRouter API key. Configure config/embeddings_config.json")

    decider_model = model or config.get("triage_model") or "~perplexity/pplx-decider-latest"

    results = []
    total_cost = 0.0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sec = {
            executor.submit(audit_parsed_section, sec, key, decider_model, threshold): sec
            for sec in sections
        }
        for future in as_completed(future_to_sec):
            res = future.result()
            results.append(res)
            total_cost += res.cost_usd

    # Preserve natural title ordering
    sec_order = {sec.title: i for i, sec in enumerate(sections)}
    results.sort(key=lambda r: sec_order.get(r.section_title, 999))

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    total_breaches = sum(len(r.breaches) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    return EpistemicAuditReport(
        total_sections=len(results),
        passed_sections=passed_count,
        failed_sections=failed_count,
        total_breaches=total_breaches,
        total_warnings=total_warnings,
        total_cost_usd=round(total_cost, 5),
        results=results
    )
