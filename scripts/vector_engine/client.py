"""Embedding API client, vector serialization, and distance math."""

import json
import time
import struct
import random
import urllib.request
import urllib.error
from typing import List

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"


def is_local_ml_available() -> bool:
    """Check if local sentence-transformers package is installed."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def serialize_vector(vec: List[float]) -> bytes:
    """Pack float array into compact binary blob."""
    return struct.pack(f"{len(vec)}f", *vec)


def deserialize_vector(blob: bytes) -> List[float]:
    """Unpack binary blob back into float array."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def dot_product(v1: List[float], v2: List[float]) -> float:
    """Compute dot product / cosine similarity between normalized vectors."""
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = sum(x * x for x in v1) ** 0.5
    norm2 = sum(y * y for y in v2) ** 0.5
    if norm1 > 0 and norm2 > 0:
        return dot / (norm1 * norm2)
    return dot


def fetch_openrouter_embeddings(
    texts: List[str],
    model: str,
    api_key: str,
    endpoint: str,
    max_retries: int = 5,
    initial_backoff: float = 2.0
) -> List[List[float]]:
    """Fetch embeddings from OpenRouter via standard urllib.request.

    Guaranteed zero external library dependencies and restricted purely to /embeddings.
    Includes exponential backoff with jitter and Retry-After handling for HTTP 429 rate limits.
    """
    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key:
        raise ValueError("Invalid or placeholder OpenRouter API key found in configuration.")

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Telegram Psychological Analysis Agent"
    }

    payload = {
        "model": model,
        "input": texts
    }

    req_data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                data_items = resp_body.get("data", [])
                data_items.sort(key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in data_items]
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            # Handle rate limit (429) or transient server errors (500, 502, 503, 504)
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                retry_after_hdr = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                sleep_time = None
                if retry_after_hdr:
                    try:
                        sleep_time = float(retry_after_hdr) + random.uniform(0.5, 1.5)
                    except ValueError:
                        pass
                if sleep_time is None:
                    sleep_time = min(60.0, (initial_backoff * (2 ** attempt)) + random.uniform(0.5, 2.0))

                print(f"[!] OpenRouter HTTP {e.code} (Rate limit/busy). Backing off for {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(sleep_time)
                continue
            raise RuntimeError(f"OpenRouter HTTP {e.code} Error: {err_msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries - 1:
                sleep_time = min(30.0, (initial_backoff * (1.5 ** attempt)) + random.uniform(0.5, 1.5))
                print(f"[!] OpenRouter connection timeout/error ({e}). Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(sleep_time)
                continue
            raise RuntimeError(f"OpenRouter Connection Error: {e}")
        except Exception as e:
            raise RuntimeError(f"OpenRouter Unexpected Error: {e}")

    raise RuntimeError(f"Max retries ({max_retries}) exceeded calling OpenRouter /embeddings.")
