"""Scaledown SLM integration (summarization and candidate entity extraction)."""

import json
import time
import urllib.request
import urllib.error


def call_openrouter_summary(
    dialogue_text: str,
    model: str,
    api_key: str,
    max_retries: int = 3
) -> str:
    """Generate a dense, factual 1-2 sentence summary of the dialogue thread."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Thread Dialogue Summarization"
    }
    trimmed = dialogue_text[:16000]
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise conversation summarizer. Summarize what occurs in this conversation "
                    "in 1 to 2 factual sentences. Focus on interpersonal dynamics, emotional topics, conflicts, "
                    "or life events. Do not use filler introductions like 'In this conversation'."
                )
            },
            {"role": "user", "content": trimmed}
        ],
        "temperature": 0.2,
        "max_tokens": 120
    }
    req_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            return resp_data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter Summary API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e
    raise RuntimeError("Max retries exceeded calling call_openrouter_summary.")


def call_openrouter_extraction(
    dialogue_text: str,
    model: str,
    api_key: str,
    max_retries: int = 3
) -> str:
    """Extract candidate external individuals and relational entities from dialogue as JSON string."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Candidate Entity Extraction"
    }
    trimmed = dialogue_text[:16000]
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract all third-party human individuals mentioned or discussed in this dialogue. "
                    "Include both personal names (e.g. 'Sarah', 'Ahmed') and relational/functional descriptions (e.g. 'my ex', 'boss', 'pediatrician', 'roommate'). "
                    "Respond ONLY with a valid JSON array of objects: [{\"mention\": \"...\", \"role\": \"...\"}]. "
                    "If no third-party individuals are mentioned, respond with []."
                )
            },
            {"role": "user", "content": trimmed}
        ],
        "temperature": 0.0,
        "max_tokens": 300
    }

    if "extract" in model.lower():
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "person_entities",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "people": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "mention": {"type": "string", "description": "Name or relational mention"},
                                    "role": {"type": "string", "description": "Role or relationship"}
                                },
                                "required": ["mention", "role"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["people"],
                    "additionalProperties": False
                }
            }
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
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    if "structured_result" in parsed and isinstance(parsed["structured_result"], dict) and "people" in parsed["structured_result"]:
                        parsed = parsed["structured_result"]["people"]
                    elif "people" in parsed:
                        parsed = parsed["people"]
                    elif "entities" in parsed:
                        parsed = parsed["entities"]
                return json.dumps(parsed, ensure_ascii=False)
            except Exception:
                return json.dumps([{"mention": content[:80], "role": "unparsed"}], ensure_ascii=False)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter Extraction API error {e.code}: {err_msg}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
                continue
            raise e
    raise RuntimeError("Max retries exceeded calling call_openrouter_extraction.")
