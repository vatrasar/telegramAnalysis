"""Adversarial System-1 deciders for watchdog audits and single-thread routing."""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple

from triage_engine.decisions_client import (
    call_openrouter_decisions,
    call_openrouter_chat_completions,
)


def evaluate_single_thread(
    thread_data: Dict[str, Any],
    api_key: str,
    model: str,
    salience_threshold: float
) -> Dict[str, Any]:
    """Evaluate a single thread routing to either Decisions API or Chat API based on model type."""
    dialogue_text = thread_data["dialogue_text"]

    if not dialogue_text or len(dialogue_text.strip()) < 10:
        return {
            "thread_id": thread_data["thread_id"],
            "chat_id": thread_data["chat_id"],
            "salience_score": 0.0,
            "escalate": 0,
            "primary_category": "trivial_logistics",
            "confidence": 1.0,
            "is_atypical": 0,
            "interlocutor_surprised": 0,
            "emotional_peak": "none",
            "is_advice_seeking": 0,
            "mentions_third_party": 0,
            "anomaly_notes": "",
            "reason": "Thread empty or under 10 chars",
            "raw_response": "{}"
        }

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        res = call_openrouter_decisions(
            dialogue_text=dialogue_text,
            model=model,
            api_key=api_key,
            salience_threshold=salience_threshold
        )
    else:
        res = call_openrouter_chat_completions(
            dialogue_text=dialogue_text,
            model=model,
            api_key=api_key,
            salience_threshold=salience_threshold
        )

    res["thread_id"] = thread_data["thread_id"]
    res["chat_id"] = thread_data["chat_id"]
    return res


def verify_unregistered_entities_decider(
    dialogue_text: str,
    known_names: List[str],
    model: str,
    api_key: str,
    max_retries: int = 3
) -> Tuple[bool, float]:
    """Adversarial System-1 watchdog: verify whether dialogue mentions any third-party person NOT in known_names."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Entity Watchdog Decision"
    }

    trimmed_text = dialogue_text[:16000]
    known_str = ", ".join(f"'{name}'" for name in known_names) if known_names else "none"

    instructions = (
        f"Currently known and registered persons (with their roles and descriptors): [{known_str}].\n"
        f"Core Question: Does this conversation thread introduce, present, discuss, or mention ANY NEW, UNKNOWN PERSON "
        f"not accounted for in the list of known persons above? "
        f"(Consider both personal names and relational or functional descriptions like 'my ex', 'new suitor', 'the doctor', 'a coworker', "
        f"provided it refers to a distinct, new human individual)."
    )

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        payload = {
            "model": model,
            "state": trimmed_text,
            "questions": {
                "has_unregistered_third_party": {
                    "type": "noul",
                    "instructions": instructions
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
                prob = float(answers.get("has_unregistered_third_party", {}).get("noul", 0.0))
                return (prob >= 0.5, prob)
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
    else:
        chat_url = "https://openrouter.ai/api/v1/chat/completions"
        system_prompt = (
            "You are an adversarial entity verification watchdog. "
            "Your task is to determine whether a conversation thread introduces, presents, or mentions ANY NEW, UNKNOWN PERSON "
            "not present in the provided list of known registered persons.\n"
            "Respond ONLY with a valid JSON object: {\"has_unregistered_third_party\": boolean, \"probability\": number}"
        )
        user_prompt = f"Known registered entities: [{known_str}]\n\nDialogue text:\n{trimmed_text}\n\nQuestion: {instructions}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 100
        }
        req_data = json.dumps(payload).encode("utf-8")
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(chat_url, data=req_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                parsed = json.loads(content)
                flag = bool(parsed.get("has_unregistered_third_party", False))
                prob = float(parsed.get("probability", 1.0 if flag else 0.0))
                return (flag, prob)
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

    raise RuntimeError("Max retries exceeded calling verify_unregistered_entities_decider.")


def verify_secondary_anomaly_decider(
    dialogue_text: str,
    identified_anomalies: List[str],
    model: str,
    api_key: str,
    max_retries: int = 3
) -> Tuple[bool, float]:
    """Adversarial System-1 check: verify whether dialogue contains unaddressed/secondary behavioral or emotional anomalies."""
    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Secondary Anomaly Decision"
    }

    trimmed_text = dialogue_text[:16000]
    identified_str = "; ".join(identified_anomalies) if identified_anomalies else "none"

    instructions = (
        f"In this dialogue, the following behavioral or emotional anomaly has ALREADY been identified: [{identified_str}].\n"
        f"Core Question: Does this conversation thread contain ANY OTHER, DISTINCT, UNADDRESSED behavioral anomaly, "
        f"acute emotional breakdown, explosive argument, medical/life crisis, bizarre violation, or interlocutor shock "
        f"not covered by the already identified event(s) above?"
    )

    is_decision_model = any(k in model.lower() for k in ["decider", "decision", "jev", "systemone"])

    if is_decision_model:
        payload = {
            "model": model,
            "state": trimmed_text,
            "questions": {
                "has_secondary_anomaly": {
                    "type": "noul",
                    "instructions": instructions
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
                prob = float(answers.get("has_secondary_anomaly", {}).get("noul", 0.0))
                return (prob >= 0.5, prob)
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
    else:
        chat_url = "https://openrouter.ai/api/v1/chat/completions"
        system_prompt = (
            "You are an adversarial behavioral anomaly investigator. "
            "Your task is to determine whether a dialogue contains any SECONDARY, UNADDRESSED behavioral anomalies or acute crises "
            "beyond the ones already identified.\n"
            "Respond ONLY with a valid JSON object: {\"has_secondary_anomaly\": boolean, \"probability\": number}"
        )
        user_prompt = f"Already identified anomalies: [{identified_str}]\n\nDialogue text:\n{trimmed_text}\n\nQuestion: {instructions}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 100
        }
        req_data = json.dumps(payload).encode("utf-8")
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(chat_url, data=req_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                parsed = json.loads(content)
                flag = bool(parsed.get("has_secondary_anomaly", False))
                prob = float(parsed.get("probability", 1.0 if flag else 0.0))
                return (flag, prob)
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

    raise RuntimeError("Max retries exceeded calling verify_secondary_anomaly_decider.")
