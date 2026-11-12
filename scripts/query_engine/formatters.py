"""Text formatting and duration utilities for query output."""

import math
from typing import Optional, Any

SAFE_MESSAGE_CHAR_LIMIT = 1500


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable string (days, hours, minutes)."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h"


def format_message_text(
    text: Optional[str],
    msg_id: Optional[Any] = None,
    max_chars: int = SAFE_MESSAGE_CHAR_LIMIT
) -> str:
    """Safely format single message text with per-message truncation guard.

    Protects LLM context from being flooded by individual outlier messages (pasted texts,
    long forwardings, or articles) without restricting normal multi-message dialogue flow.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    total_parts = math.ceil(len(text) / max_chars)
    # Attempt word boundary break within the last 100 characters before limit
    trunc_point = max_chars
    last_space = text[:max_chars].rfind(" ")
    last_newline = text[:max_chars].rfind("\n")
    best_break = max(last_space, last_newline)
    if best_break > max_chars - 100:
        trunc_point = best_break

    truncated_content = text[:trunc_point].rstrip()
    id_arg = str(msg_id) if msg_id is not None else "<msg_id>"
    warning_notice = (
        f"\n\n... [⚠️ WIADOMOŚĆ UCIĘTA: Wyświetlono {len(truncated_content)} z {len(text)} znaków (Część 1/{total_parts}).\n"
        f"    Aby przeczytać pełną treść lub kolejne części, użyj:\n"
        f"    python3 project/scripts/query_chat.py -m {id_arg} --part 2 (lub --all)]"
    )
    return truncated_content + warning_notice
