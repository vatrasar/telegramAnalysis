#!/usr/bin/env python3
"""
Configuration Initializer & Pre-Flight Validator.
Ensures config/embeddings_config.json exists above project/ in the workspace root,
validates user-provided API credentials, and tests connectivity to OpenRouter.
"""

import os
import sys
import json
import shutil
import urllib.request
import urllib.error

# Workspace root is above the project/ directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # project/scripts
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)               # project
ROOT_DIR = os.path.dirname(PROJECT_DIR)                  # workspace root

CONFIG_DIR = os.path.join(ROOT_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "embeddings_config.json")
TEMPLATE_PATH = os.path.join(CONFIG_DIR, "embeddings_config.template.json")


def init_config() -> int:
    """Initialize config file in the workspace root and validate readiness."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # 1. Check if config file exists
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(TEMPLATE_PATH):
            shutil.copy(TEMPLATE_PATH, CONFIG_PATH)
        else:
            default_conf = {
                "provider": "openrouter",
                "api_key": "YOUR_OPENROUTER_API_KEY_HERE",
                "model": "openai/text-embedding-3-small",
                "endpoint": "https://openrouter.ai/api/v1/embeddings",
                "batch_size": 50
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_conf, f, indent=2)

        print("[ACTION_REQUIRED] Config file created at: config/embeddings_config.json")
        print("  -> Please open this file and enter your OpenRouter API key and preferred model.")
        print("  -> (This file is protected in .gitignore and will NEVER be committed to Git).")
        return 2

    # 2. Parse existing config
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to parse config/embeddings_config.json: {e}")
        print("  -> Please verify the JSON syntax or delete the file to regenerate a clean template.")
        return 1

    provider = str(config.get("provider", "openrouter")).lower()

    # 3. Validate OpenRouter Provider
    if provider in ("openrouter", "api", "openai"):
        api_key = str(config.get("api_key", "")).strip()
        model = str(config.get("model", "openai/text-embedding-3-small")).strip()
        endpoint = str(config.get("endpoint", "https://openrouter.ai/api/v1/embeddings")).strip()

        if not api_key or "YOUR_OPENROUTER_API_KEY" in api_key or api_key.startswith("YOUR_"):
            print("[ACTION_REQUIRED] OpenRouter API key has not been set yet!")
            print(f"  -> File: config/embeddings_config.json")
            print("  -> Please replace 'YOUR_OPENROUTER_API_KEY_HERE' with your real OpenRouter API key.")
            return 2

        # 4. Perform live connectivity and auth test
        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"[*] Testing OpenRouter connectivity (Model: {model}, Key: {masked_key})...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/vatrasar/telegramAnalysis",
            "X-Title": "Preflight Check"
        }
        test_payload = json.dumps({"model": model, "input": "test"}).encode("utf-8")
        req = urllib.request.Request(endpoint, data=test_payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                if "data" in resp_json and len(resp_json["data"]) > 0:
                    print(f"[SUCCESS] OpenRouter connection verified! Model '{model}' is active and ready.")
                    return 0
                else:
                    print(f"[WARNING] Unexpected response from OpenRouter: {resp_json}")
                    return 0
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code == 401:
                print(f"[ERROR] HTTP 401 Unauthorized: The OpenRouter API key is invalid or expired.")
                print("  -> Please check the API key in config/embeddings_config.json.")
                return 3
            elif e.code == 402:
                print(f"[ERROR] HTTP 402 Payment Required: Insufficient balance/credits on OpenRouter account.")
                print("  -> Please add credits at https://openrouter.ai/credits or check key credit limits.")
                return 4
            elif e.code == 404:
                print(f"[ERROR] HTTP 404 Not Found: The model '{model}' does not exist on OpenRouter.")
                print("  -> Check available models at https://openrouter.ai/models (e.g. 'openai/text-embedding-3-small').")
                return 5
            else:
                print(f"[ERROR] OpenRouter HTTP {e.code} Error: {err_body}")
                return 1
        except urllib.error.URLError as e:
            print(f"[ERROR] Network Connection Failure: Unable to reach {endpoint} ({e.reason}).")
            print("  -> Please verify your internet connection or proxy settings.")
            return 6
        except Exception as e:
            print(f"[ERROR] Unexpected test failure: {e}")
            return 1

    # 5. Validate Local Provider
    elif provider == "local":
        model_name = config.get("model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        try:
            import sentence_transformers
            print(f"[SUCCESS] Local sentence-transformers installed. Model '{model_name}' ready.")
            return 0
        except ImportError:
            print("[ERROR] 'provider' is set to 'local', but 'sentence-transformers' is not installed.")
            print("  -> Run: pip install sentence-transformers")
            print("  -> Or switch 'provider' to 'openrouter' in config/embeddings_config.json")
            return 7
    else:
        print(f"[ERROR] Unknown provider '{provider}' in config/embeddings_config.json.")
        return 1


if __name__ == "__main__":
    code = init_config()
    sys.exit(code)
