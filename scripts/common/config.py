"""Configuration loading utilities."""

import os
import json
from typing import Dict, Any, Optional


def get_workspace_root() -> str:
    """Find the workspace root directory (above project/)."""
    current = os.path.dirname(os.path.abspath(__file__))
    # Ascend until we find a parent that contains 'config' or 'project'
    while current and current != os.path.dirname(current):
        if os.path.isdir(os.path.join(current, "config")) or os.path.isdir(os.path.join(current, "project")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()


def get_config_path(override_path: Optional[str] = None) -> str:
    """Locate embeddings_config.json in config/."""
    if override_path and os.path.exists(override_path):
        return override_path
    
    root = get_workspace_root()
    candidate = os.path.join(root, "config", "embeddings_config.json")
    if os.path.exists(candidate):
        return candidate
    
    cwd_candidate = os.path.join(os.getcwd(), "config", "embeddings_config.json")
    if os.path.exists(cwd_candidate):
        return cwd_candidate
        
    return candidate


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from config/embeddings_config.json."""
    resolved_path = get_config_path(config_path)
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(
            f"Config file missing at: {resolved_path}\n"
            f"Run 'python3 project/scripts/setup_config.py' to generate a clean template."
        )
    with open(resolved_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_api_key(config: Optional[Dict[str, Any]] = None) -> str:
    """Extract and validate OpenRouter API key from configuration."""
    cfg = config or load_config()
    api_key = str(cfg.get("api_key", "")).strip()
    return api_key
