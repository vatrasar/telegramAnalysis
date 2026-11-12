"""Scaledown SLM integration (summarization and candidate entity extraction)."""

import json
import time
from typing import Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    _SESSION: Optional[requests.Session] = None

    def get_requests_session() -> requests.Session:
        global _SESSION
        if _SESSION is None:
            _SESSION = requests.Session()
            adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64)
            _SESSION.mount("https://", adapter)
            _SESSION.mount("http://", adapter)
        return _SESSION
except ImportError:
    requests = None
    get_requests_session = None

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

    if requests is not None:
        session = get_requests_session()
        for attempt in range(max_retries):
            try:
                resp = session.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 429 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                if resp.status_code != 200:
                    raise RuntimeError(f"OpenRouter Summary API error {resp.status_code}: {resp.text}")
                resp_data = resp.json()
                return resp_data["choices"][0]["message"]["content"].strip()
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(1.5 ** attempt)
                    continue
                raise RuntimeError(f"OpenRouter Summary connection failure: {e}")
        raise RuntimeError("Max retries exceeded calling call_openrouter_summary.")

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

    def _parse_content(content: str) -> str:
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

    if requests is not None:
        session = get_requests_session()
        for attempt in range(max_retries):
            try:
                resp = session.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 429 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                if resp.status_code != 200:
                    raise RuntimeError(f"OpenRouter Extraction API error {resp.status_code}: {resp.text}")
                resp_data = resp.json()
                content = resp_data["choices"][0]["message"]["content"].strip()
                return _parse_content(content)
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(1.5 ** attempt)
                    continue
                raise RuntimeError(f"OpenRouter Extraction connection failure: {e}")
        raise RuntimeError("Max retries exceeded calling call_openrouter_extraction.")

    req_data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            content = resp_data["choices"][0]["message"]["content"].strip()
            return _parse_content(content)
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

