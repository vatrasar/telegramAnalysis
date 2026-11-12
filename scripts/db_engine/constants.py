"""Constants and thresholds for Telegram conversation disentangling and database building."""

import re
from typing import Dict, Any, Optional

BURST_THRESHOLD_SECONDS = 180       # 3 minutes: burst continuation threshold
INFERRED_RESPONSE_SECONDS = 3600    # 60 minutes: inferred response without explicit quote
SESSION_GAP_SECONDS = 7200          # 2 hours: silence threshold for new conversation session
LONG_SILENCE_SECONDS = 86400        # 24 hours: threshold for relationship silence analysis
MAX_THREAD_MESSAGES = 50            # 50 messages: strict message limit per conversation thread


def derive_chat_id(data: Dict[str, Any], filepath: str, explicit_id: Optional[str] = None) -> str:
    """Generate a clean, collision-free chat identifier."""
    if explicit_id:
        clean = re.sub(r"[^\w]+", "_", explicit_id).strip("_").lower()
        return clean if clean.startswith("c_") else f"c_{clean}"

    raw_id = data.get("id")
    if raw_id is not None and str(raw_id).strip() != "":
        clean_id = str(raw_id).strip().replace("-", "m")
        return f"c_{clean_id}"

    import os
    base = os.path.splitext(os.path.basename(filepath))[0]
    clean_stem = re.sub(r"[^\w]+", "_", base).strip("_").lower()
    return f"c_{clean_stem}" if clean_stem else "c_default"
