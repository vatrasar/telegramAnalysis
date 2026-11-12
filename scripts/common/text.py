"""Text parsing, hashing, and date utilities."""

import hashlib
from datetime import datetime
from typing import Any, Tuple


def extract_text(raw_text: Any) -> str:
    """Extract plain text from Telegram JSON text field (string or rich-text list)."""
    if isinstance(raw_text, str):
        return raw_text.strip()
    elif isinstance(raw_text, list):
        parts = []
        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts).strip()
    return ""


def parse_iso_date(date_str: str) -> Tuple[datetime, int]:
    """Parse ISO date string and return datetime object and unix epoch timestamp."""
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        clean = date_str.replace("Z", "").replace(" ", "T")
        dt = datetime.fromisoformat(clean)
    return dt, int(dt.timestamp())


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file efficiently in 64KB chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a clean human-readable string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        return f"{days}d {hours}h" if hours > 0 else f"{days}d"
