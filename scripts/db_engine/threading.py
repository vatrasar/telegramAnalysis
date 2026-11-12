"""Dialogue thread disentanglement using RAT-FBP (Reply-Anchored Threading with Forward Burst Propagation)."""

from typing import List, Dict, Any, Optional, Tuple
from common.text import extract_text, parse_iso_date
from db_engine.constants import (
    BURST_THRESHOLD_SECONDS,
    INFERRED_RESPONSE_SECONDS,
    SESSION_GAP_SECONDS,
    MAX_THREAD_MESSAGES,
)


def disentangle_threads(
    messages: List[Dict[str, Any]],
    chat_id: str,
    burst_threshold: int = BURST_THRESHOLD_SECONDS,
    inferred_gap: int = INFERRED_RESPONSE_SECONDS,
    session_gap: int = SESSION_GAP_SECONDS,
    max_thread_messages: int = MAX_THREAD_MESSAGES
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Apply Reply-Anchored Threading with Forward Burst Propagation (RAT-FBP)
    scoped to a single chat stream, enforcing a strict message limit per thread
    with parent-child lineage tracking.
    """
    valid_msgs = []
    for m in messages:
        if m.get("type") != "message":
            continue
        text = extract_text(m.get("text", ""))
        if not text:
            media_type = m.get("media_type") or m.get("photo") or m.get("file")
            if media_type:
                text = f"[{m.get('media_type', 'Media/Attachment')}]"
            else:
                continue

        sender = m.get("from") or m.get("actor") or "Unknown"
        sender_id = str(m.get("from_id") or "")
        msg_id = m.get("id")
        date_str = m.get("date")

        reply_to_id = m.get("reply_to_message_id")
        if not reply_to_id and isinstance(m.get("reply_to"), dict):
            reply_to_id = m.get("reply_to", {}).get("reply_to_message_id")

        if msg_id is None or not date_str:
            continue

        dt, ts = parse_iso_date(date_str)
        valid_msgs.append({
            "chat_id": chat_id,
            "id": int(msg_id),
            "date": date_str,
            "datetime": dt,
            "timestamp": ts,
            "sender": sender,
            "sender_id": sender_id,
            "reply_to_id": int(reply_to_id) if reply_to_id else None,
            "text": text,
            "char_count": len(text),
            "word_count": len(text.split())
        })

    valid_msgs.sort(key=lambda x: x["timestamp"])
    msg_dict = {m["id"]: m for m in valid_msgs}

    # First pass: establish parentage & link types
    last_msg_per_sender: Dict[str, int] = {}
    last_msg_overall: Optional[Dict[str, Any]] = None

    for m in valid_msgs:
        m_id = m["id"]
        ts = m["timestamp"]
        sender = m["sender"]
        reply_to = m["reply_to_id"]

        parent_id: Optional[int] = None
        link_type = "root"

        gap_before = ts - last_msg_overall["timestamp"] if last_msg_overall else 0
        m["gap_before"] = gap_before

        if reply_to and reply_to in msg_dict:
            parent_id = reply_to
            link_type = "explicit_reply"
        elif last_msg_overall and last_msg_overall["sender"] == sender and (ts - last_msg_overall["timestamp"] <= burst_threshold):
            parent_id = last_msg_overall["id"]
            link_type = "burst_continuation"
        elif (
            sender in last_msg_per_sender
            and (ts - msg_dict[last_msg_per_sender[sender]]["timestamp"] <= burst_threshold)
        ):
            parent_id = last_msg_per_sender[sender]
            link_type = "burst_continuation"
        elif last_msg_overall and gap_before <= inferred_gap:
            parent_id = last_msg_overall["id"]
            link_type = "inferred_response"
        else:
            link_type = "session_root" if gap_before >= session_gap else "topic_root"
            parent_id = None

        m["parent_id"] = parent_id
        m["link_type"] = link_type
        last_msg_per_sender[sender] = m_id
        last_msg_overall = m

    # Second pass: Initial thread assignment & Topic clustering
    # Clean invariant: If message B has parent_id A (explicit quote, burst continuation, or inferred response),
    # B is directly assigned to the topic cluster of message A.
    thread_map: Dict[int, str] = {}
    thread_prefix = f"{chat_id}_t"

    for m in valid_msgs:
        m_id = m["id"]
        p_id = m["parent_id"]

        if p_id and p_id in thread_map:
            t_id = thread_map[p_id]
        else:
            t_id = f"{thread_prefix}{m_id}"

        thread_map[m_id] = t_id
        m["thread_id"] = t_id

    # Group messages into initial threads
    raw_threads: Dict[str, List[Dict[str, Any]]] = {}
    for m in valid_msgs:
        t_id = m["thread_id"]
        if t_id not in raw_threads:
            raw_threads[t_id] = []
        raw_threads[t_id].append(m)

    # Third pass: Enforce max_thread_messages limit and build parent-child lineage
    threads_data: Dict[str, Dict[str, Any]] = {}

    for raw_t_id, msgs in raw_threads.items():
        if len(msgs) <= max_thread_messages:
            threads_data[raw_t_id] = {
                "thread_id": raw_t_id,
                "parent_thread_id": None,
                "anchor_id": None,
                "messages": msgs
            }
        else:
            # Partition oversized thread into linked chunks
            prev_chunk_id: Optional[str] = None
            for idx, i in enumerate(range(0, len(msgs), max_thread_messages)):
                chunk_msgs = msgs[i:i + max_thread_messages]
                chunk_id = raw_t_id if idx == 0 else f"{raw_t_id}_p{idx + 1}"

                # Update message thread_id so database rows accurately reflect sub-thread partition
                for m in chunk_msgs:
                    m["thread_id"] = chunk_id

                threads_data[chunk_id] = {
                    "thread_id": chunk_id,
                    "parent_thread_id": prev_chunk_id,
                    "anchor_id": None,
                    "messages": chunk_msgs
                }
                prev_chunk_id = chunk_id

    return valid_msgs, threads_data
