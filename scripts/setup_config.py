#!/usr/bin/env python3
"""
Configuration Initializer & Pre-Flight Validator.
Ensures config/embeddings_config.json exists above .agents/ in the workspace root,
validates user-provided OpenRouter API credentials, and tests connectivity
for both the Embeddings model and the System-1 Triage/Decider model.
"""

import os
import sys
import json
import shutil
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any

# Workspace root is above the agent package directory (.agents/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # .agents/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # .agents
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root

CONFIG_DIR = os.path.join(ROOT_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "embeddings_config.json")
TEMPLATE_PATH = os.path.join(CONFIG_DIR, "embeddings_config.template.json")


def init_and_load_config() -> Dict[str, Any]:
    """Ensure config exists and load it."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(TEMPLATE_PATH):
            shutil.copy(TEMPLATE_PATH, CONFIG_PATH)
        else:
            default_conf = {
                "api_key": "YOUR_OPENROUTER_API_KEY_HERE",
                "model": "qwen/qwen3-embedding-8b",
                "triage_model": "perplexity/pplx-decider-v1.2"
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_conf, f, indent=2)

        print("[ACTION_REQUIRED] Config file created at: config/embeddings_config.json")
        print("  -> Please open this file and enter your OpenRouter API key and preferred models.")
        sys.exit(2)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to parse config/embeddings_config.json: {e}")
        sys.exit(1)

    return config


def test_embeddings_connectivity(api_key: str, model: str) -> int:
    """Test OpenRouter embeddings endpoint."""
    endpoint = "https://openrouter.ai/api/v1/embeddings"
    masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"[*] Testing Embeddings Model (Model: {model}, Key: {masked_key})...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Embeddings Preflight Check"
    }
    test_payload = json.dumps({"model": model, "input": "test"}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=test_payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
            if "data" in resp_json and len(resp_json["data"]) > 0:
                print(f"[SUCCESS] Embeddings verified! Model '{model}' is active and ready.")
                return 0
            else:
                print(f"[WARNING] Unexpected response from Embeddings endpoint: {resp_json}")
                return 0
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            print(f"[ERROR] HTTP 401 Unauthorized: The OpenRouter API key is invalid or expired.")
            return 3
        elif e.code == 402:
            print(f"[ERROR] HTTP 402 Payment Required: Insufficient balance/credits on OpenRouter account.")
            return 4
        elif e.code == 404:
            print(f"[ERROR] HTTP 404 Not Found: Embeddings model '{model}' does not exist on OpenRouter.")
            return 5
        else:
            print(f"[ERROR] Embeddings HTTP {e.code} Error: {err_body}")
            return 1
    except Exception as e:
        print(f"[ERROR] Embeddings connection failure: {e}")
        return 6


def test_triage_connectivity(api_key: str, triage_model: str) -> int:
    """Test OpenRouter System-1 triage router endpoint (supporting Decisions API & Chat Completions)."""
    masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"[*] Testing System-1 Triage Router (Model: {triage_model}, Key: {masked_key})...")

    is_decision_model = any(keyword in triage_model.lower() for keyword in ["decider", "decision", "jev", "systemone"])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
        "X-Title": "Triage Preflight Check"
    }

    if is_decision_model:
        # OpenRouter Alpha Decisions API
        endpoint = "https://openrouter.ai/api/alpha/decisions"
        test_payload = json.dumps({
            "model": triage_model,
            "state": "Testing System-1 triage connectivity.",
            "questions": {
                "is_test": {
                    "type": "noul",
                    "instructions": "Is this a test message?"
                }
            }
        }).encode("utf-8")
    else:
        # Standard Chat Completions API
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        test_payload = json.dumps({
            "model": triage_model,
            "messages": [
                {"role": "user", "content": "Respond with JSON: {\"status\": \"ok\"}"}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 20
        }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=test_payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
            if ("answers" in resp_json) or ("choices" in resp_json and len(resp_json["choices"]) > 0):
                print(f"[SUCCESS] System-1 Triage model verified! Model '{triage_model}' is active.")
                return 0
            else:
                print(f"[WARNING] Unexpected response from Triage endpoint: {resp_json}")
                return 0
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            print(f"[ERROR] HTTP 401 Unauthorized: The OpenRouter API key is invalid.")
            return 3
        elif e.code == 402:
            print(f"[ERROR] HTTP 402 Payment Required: Insufficient OpenRouter credits.")
            return 4
        elif e.code == 404:
            print(f"[ERROR] HTTP 404 Not Found: Triage model '{triage_model}' not found on OpenRouter.")
            return 5
        else:
            print(f"[ERROR] Triage Router HTTP {e.code} Error: {err_body}")
            return 1
    except Exception as e:
        print(f"[ERROR] Triage Router connection failure: {e}")
        return 6


def main() -> int:
    parser = argparse.ArgumentParser(description="Configuration Initializer & Pre-Flight Validator")
    parser.add_argument("--embeddings", action="store_true", help="Validate only embeddings connectivity")
    parser.add_argument("--triage", action="store_true", help="Validate only System-1 triage model connectivity")
    args = parser.parse_args()

    config = init_and_load_config()

    api_key = str(config.get("api_key", "")).strip()
    embeddings_model = str(config.get("model", "qwen/qwen3-embedding-8b")).strip()
    triage_model = str(config.get("triage_model", "perplexity/pplx-decider-v1.2")).strip()

    if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key or api_key.startswith("YOUR_"):
        print("[ACTION_REQUIRED] OpenRouter API key has not been set yet!")
        print(f"  -> File: config/embeddings_config.json")
        print("  -> Please replace placeholder with your real OpenRouter API key.")
        return 2

    check_embeddings = args.embeddings or (not args.triage)
    check_triage = args.triage or (not args.embeddings)

    codes = []
    print("=" * 70)
    print("🔍 PRE-FLIGHT OPENROUTER CONFIG VALIDATION (config/embeddings_config.json)")
    print("=" * 70)

    if check_embeddings:
        codes.append(test_embeddings_connectivity(api_key, embeddings_model))

    if check_triage:
        codes.append(test_triage_connectivity(api_key, triage_model))

    return max(codes) if codes else 0


if __name__ == "__main__":
    sys.exit(main())
