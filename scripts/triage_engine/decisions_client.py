"""OpenRouter API client for Decisions API and Chat Completions triage."""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any


def call_openrouter_decisions(
    dialogue_text: str,
    model: str,
    api_key: str,
    salience_threshold: float,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Call OpenRouter Decisions API (POST /api/alpha/decisions) for native System-1 decision models."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Thread Triage Decisions"
    }

    trimmed_text = dialogue_text[:20000]

    payload = {
        "model": model,
        "state": trimmed_text,
        "questions": {
            "escalate_to_llm": {
                "type": "noul",
                "instructions": (
                    "Does this conversation thread contain substantive psychological, emotional, "
                    "biographical, relational, or ideological content worth analyzing?"
                )
            },
            "salience_score": {
                "type": "score",
                "instructions": "Rate the psychological diagnostic relevance and substantive depth of this dialogue.",
                "criteria": [
                    "Pure noise: routine greetings, short scheduling, links/memes without comment, trivial small talk",
                    "Low relevance: casual chitchat with minimal personal or emotional substance",
                    "Moderate: noticeable emotional expression, interpersonal dynamic, or personal life reflection",
                    "High: significant disclosure, vulnerability, emotional conflict, or core worldview assertion",
                    "Critical: foundational trauma, formative life turning point, or major relational rupture"
                ]
            },
            "primary_category": {
                "type": "choice",
                "instructions": "What is the primary psychological category of this dialogue?",
                "criteria": {
                    "trivial_logistics": "Routine scheduling, greetings, links without comment",
                    "biographical_fact": "Biographical facts, family background, health, career milestones",
                    "emotional_vulnerability": "Vulnerability, fear, shame, grief, emotional confessions",
                    "relational_conflict_or_boundary": "Friction, arguments, emotional coldness, boundary setting",
                    "values_and_worldview": "Core beliefs, moral stances, worldview, philosophy",
                    "defense_or_coping": "Psychological defenses, rationalization, projection, avoidance"
                }
            },
            "is_atypical": {
                "type": "noul",
                "instructions": (
                    "Do the behaviors, declarations, stories, or emotional reactions deviate markedly "
                    "from normal social or conversational baselines (e.g. bizarre claims, violent outbursts, taboo disclosures)?"
                )
            },
            "interlocutor_surprised": {
                "type": "noul",
                "instructions": (
                    "Does any interlocutor exhibit shock, disbelief, cognitive dissonance, confusion, "
                    "or call out unexpected behavior ('wait what?', 'seriously?', 'since when?')?"
                )
            },
            "emotional_peak": {
                "type": "choice",
                "instructions": (
                    "Does this dialogue contain an acute emotional peak or grave emotional situation "
                    "(either from direct intense feelings, tragic medical/life disclosures, or deep empathetic distress, condolences, and consoling from the interlocutor)?"
                ),
                "criteria": {
                    "none": "Routine emotional baseline, mild everyday feelings, calm conversation, or intellectual debates",
                    "profound_sadness": "Acute grief, heartbreak, despair, crying, tragic illness/family news, or deep empathetic condolences/consoling",
                    "euphoric_joy": "Intense joy, celebration, euphoric breakthrough, falling in love, relief",
                    "intense_rage": "Explosive fury, extreme indignation, verbal aggression, loss of temper"
                }
            },
            "is_advice_seeking": {
                "type": "noul",
                "instructions": (
                    "Does a participant explicitly ask for advice on a personal problem, express a moral/life dilemma ('what should I do?'), "
                    "or announce an intimate personal confession ('I need to confess something', 'can I tell you something in confidence')?"
                )
            },
            "mentions_third_party_person": {
                "type": "noul",
                "instructions": (
                    "Does this dialogue explicitly mention, discuss, quote, or introduce an external third-party person "
                    "(e.g. friend, suitor, ex-partner, coworker, boss, family member, acquaintance) other than the two main chat participants?"
                )
            },
            "is_relational_conflict": {
                "type": "noul",
                "instructions": (
                    "Does this dialogue contain severe relational friction, an intense argument, verbal hostility, "
                    "abrupt emotional coldness, or a rupture/breakup between participants or with an external person?"
                )
            },
            "is_medical_or_grief_crisis": {
                "type": "noul",
                "instructions": (
                    "Does this dialogue discuss or disclose a grave medical emergency, serious illness, hospitalization, "
                    "physical injury, tragic loss, death, or acute bereavement/grief?"
                )
            },
            "is_bizarre_or_boundary_violation": {
                "type": "noul",
                "instructions": (
                    "Do the behaviors, disclosures, or stories involve marked violations of social boundaries, bizarre/paranoid claims, "
                    "stalking, illicit/taboo acts, or extreme eccentricities deviating sharply from normal conversational baselines?"
                )
            },
            "is_acute_vulnerability_or_breakdown": {
                "type": "noul",
                "instructions": (
                    "Does a participant experience an acute emotional breakdown, intense panic, uncontrollable crying, "
                    "profound helplessness, or make a painful, vulnerable confession of shame or guilt?"
                )
            }
        }
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            answers = resp_data.get("answers", {})

            esc_noul = float(answers.get("escalate_to_llm", {}).get("noul", 0.0))
            score_data = answers.get("salience_score", {})
            score = float(score_data.get("score", 0.0))
            confidence = float(score_data.get("confidence", 0.8))

            cat_data = answers.get("primary_category", {})
            cat = str(cat_data.get("choice", cat_data.get("value", "trivial_logistics")))

            is_atypical = 1 if float(answers.get("is_atypical", {}).get("noul", 0.0)) >= 0.5 else 0
            interlocutor_surprised = 1 if float(answers.get("interlocutor_surprised", {}).get("noul", 0.0)) >= 0.5 else 0

            peak_data = answers.get("emotional_peak", {})
            emotional_peak = str(peak_data.get("choice", peak_data.get("value", "none")))
            if emotional_peak not in ("none", "profound_sadness", "euphoric_joy", "intense_rage"):
                emotional_peak = "none"

            is_advice_seeking = 1 if float(answers.get("is_advice_seeking", {}).get("noul", 0.0)) >= 0.5 else 0
            mentions_third_party = 1 if float(answers.get("mentions_third_party_person", {}).get("noul", 0.0)) >= 0.5 else 0

            is_relational_conflict = 1 if float(answers.get("is_relational_conflict", {}).get("noul", 0.0)) >= 0.5 else 0
            is_medical_or_grief_crisis = 1 if float(answers.get("is_medical_or_grief_crisis", {}).get("noul", 0.0)) >= 0.5 else 0
            is_bizarre_or_boundary_violation = 1 if float(answers.get("is_bizarre_or_boundary_violation", {}).get("noul", 0.0)) >= 0.5 else 0
            is_acute_vulnerability_or_breakdown = 1 if float(answers.get("is_acute_vulnerability_or_breakdown", {}).get("noul", 0.0)) >= 0.5 else 0

            has_special_flag = (
                (is_atypical == 1) or (interlocutor_surprised == 1) or (emotional_peak != "none") or
                (is_advice_seeking == 1) or (is_relational_conflict == 1) or (is_medical_or_grief_crisis == 1) or
                (is_bizarre_or_boundary_violation == 1) or (is_acute_vulnerability_or_breakdown == 1)
            )
            if has_special_flag:
                should_escalate = True
                score = max(score, 2.5)
            else:
                should_escalate = (esc_noul >= 0.5) or (score >= salience_threshold)
                if cat == "trivial_logistics" and score < 1.2:
                    should_escalate = False

            reason_parts = [f"cat={cat}", f"score={score:.2f}", f"esc={esc_noul:.2f}"]
            if is_atypical:
                reason_parts.append("atypical_behavior")
            if interlocutor_surprised:
                reason_parts.append("interlocutor_shock")
            if emotional_peak != "none":
                reason_parts.append(f"peak:{emotional_peak}")
            if is_advice_seeking:
                reason_parts.append("advice/confession")
            if mentions_third_party:
                reason_parts.append("third_party")
            if is_relational_conflict:
                reason_parts.append("relational_conflict")
            if is_medical_or_grief_crisis:
                reason_parts.append("medical_crisis")
            if is_bizarre_or_boundary_violation:
                reason_parts.append("boundary_violation")
            if is_acute_vulnerability_or_breakdown:
                reason_parts.append("acute_breakdown")

            notes_parts = []
            if is_relational_conflict:
                notes_parts.append("Relational conflict")
            if is_medical_or_grief_crisis:
                notes_parts.append("Medical/grief crisis")
            if is_bizarre_or_boundary_violation:
                notes_parts.append("Bizarre/boundary violation")
            if is_acute_vulnerability_or_breakdown:
                notes_parts.append("Acute vulnerability/breakdown")
            if is_atypical and not is_bizarre_or_boundary_violation:
                notes_parts.append("Atypical behavior")
            if interlocutor_surprised:
                notes_parts.append("Interlocutor surprised")
            if emotional_peak != "none":
                notes_parts.append(f"Peak: {emotional_peak}")
            if is_advice_seeking:
                notes_parts.append("Advice seeking/confession")
            if mentions_third_party:
                notes_parts.append("Mentions third party")

            return {
                "escalate": 1 if should_escalate else 0,
                "salience_score": round(score, 2),
                "confidence": round(confidence, 3),
                "primary_category": cat,
                "is_atypical": is_atypical,
                "interlocutor_surprised": interlocutor_surprised,
                "emotional_peak": emotional_peak,
                "is_advice_seeking": is_advice_seeking,
                "mentions_third_party": mentions_third_party,
                "is_relational_conflict": is_relational_conflict,
                "is_medical_or_grief_crisis": is_medical_or_grief_crisis,
                "is_bizarre_or_boundary_violation": is_bizarre_or_boundary_violation,
                "is_acute_vulnerability_or_breakdown": is_acute_vulnerability_or_breakdown,
                "anomaly_notes": ", ".join(notes_parts),
                "reason": ", ".join(reason_parts),
                "raw_response": json.dumps(resp_data)
            }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Decisions API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e

    raise RuntimeError("Max retries exceeded calling OpenRouter Decisions API.")


def call_openrouter_chat_completions(
    dialogue_text: str,
    model: str,
    api_key: str,
    salience_threshold: float,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Call OpenRouter Chat Completions endpoint with JSON output for standard LLMs."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Thread Triage Chat"
    }

    trimmed_text = dialogue_text[:16000]

    system_prompt = (
        "You are an ultra-fast, high-precision psychological triage classifier (System 1 classifier). "
        "Evaluate whether a chat conversation thread contains substantive psychological, biographical, "
        "emotional, relational, or ideological content worth analyzing for a deep personality profile, "
        "or whether it is trivial chitchat, memes, or logistics.\n\n"
        "Crucial Diagnostic Radars:\n"
        "1. is_atypical: Set true if behaviors, declarations, stories, or emotional reactions deviate markedly "
        "from standard social/conversational baselines (e.g. bizarre claims, disproportionate aggression, taboo disclosures).\n"
        "2. interlocutor_surprised: Set true if any interlocutor exhibits shock, disbelief, cognitive dissonance, "
        "confusion, or explicitly calls out unexpected behavior ('wait what?', 'seriously?', 'since when?').\n"
        "3. emotional_peak: Set to 'profound_sadness' (acute grief, tragic news, crying, deep condolences/consoling by interlocutor), "
        "'euphoric_joy' (intense happiness, celebration, infatuation, relief), 'intense_rage' (fury, verbal aggression), or 'none'.\n"
        "4. is_advice_seeking: Set true if a participant explicitly asks for advice, expresses a personal dilemma ('what should I do?'), "
        "or announces an intimate confession ('I need to confess something').\n"
        "5. mentions_third_party: Set true if this dialogue explicitly mentions, discusses, quotes, or introduces an external third-party person "
        "(e.g. friend, suitor, ex-partner, coworker, boss, family member, acquaintance) other than the two main chat participants.\n\n"
        "Respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "escalate_to_llm": boolean,\n'
        '  "salience_score": number (0.0 to 4.0),\n'
        '  "confidence": number (0.0 to 1.0),\n'
        '  "primary_category": "trivial_logistics" | "biographical_fact" | "emotional_vulnerability" | "relational_conflict_or_boundary" | "values_and_worldview" | "defense_or_coping",\n'
        '  "is_atypical": boolean,\n'
        '  "interlocutor_surprised": boolean,\n'
        '  "emotional_peak": "none" | "profound_sadness" | "euphoric_joy" | "intense_rage",\n'
        '  "is_advice_seeking": boolean,\n'
        '  "mentions_third_party": boolean,\n'
        '  "anomaly_notes": "Short 1-sentence description if special radars triggered, otherwise empty string",\n'
        '  "reason": "1-sentence concise diagnostic rationale"\n'
        "}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Evaluate this conversation thread:\n\n{trimmed_text}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 250
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            content = resp_data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:].strip()
            parsed = json.loads(content)

            score = float(parsed.get("salience_score", 0.0))
            escalate_bool = bool(parsed.get("escalate_to_llm", False))
            cat = str(parsed.get("primary_category", "trivial_logistics"))
            confidence = float(parsed.get("confidence", 0.8))
            reason = str(parsed.get("reason", ""))
            is_atypical = bool(parsed.get("is_atypical", False))
            interlocutor_surprised = bool(parsed.get("interlocutor_surprised", False))
            emotional_peak = str(parsed.get("emotional_peak", "none"))
            if emotional_peak not in ("none", "profound_sadness", "euphoric_joy", "intense_rage"):
                emotional_peak = "none"
            is_advice_seeking = bool(parsed.get("is_advice_seeking", False))
            mentions_third_party = bool(parsed.get("mentions_third_party", False))
            anomaly_notes = str(parsed.get("anomaly_notes", "")).strip()

            has_special_flag = is_atypical or interlocutor_surprised or (emotional_peak != "none") or is_advice_seeking
            if has_special_flag:
                should_escalate = True
                score = max(score, 2.5)
            else:
                should_escalate = escalate_bool or (score >= salience_threshold)
                if cat == "trivial_logistics" and score < 1.2:
                    should_escalate = False

            return {
                "escalate": 1 if should_escalate else 0,
                "salience_score": round(score, 2),
                "confidence": round(confidence, 3),
                "primary_category": cat,
                "is_atypical": 1 if is_atypical else 0,
                "interlocutor_surprised": 1 if interlocutor_surprised else 0,
                "emotional_peak": emotional_peak,
                "is_advice_seeking": 1 if is_advice_seeking else 0,
                "mentions_third_party": 1 if mentions_third_party else 0,
                "anomaly_notes": anomaly_notes,
                "reason": reason,
                "raw_response": content
            }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter Chat API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e

    raise RuntimeError("Max retries exceeded calling OpenRouter API.")
