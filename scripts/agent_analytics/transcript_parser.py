"""Transcript parser for Antigravity agent sessions and subagent hierarchies."""

import os
import re
import json
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

DEFAULT_BRAIN_DIR = "/home/vatrasar/.gemini/antigravity/brain"


def resolve_conversation_path(
    conv_id_or_path: str,
    brain_dir: str = DEFAULT_BRAIN_DIR
) -> Optional[str]:
    """Resolve a conversation ID or file path to an existing transcript.jsonl path."""
    if not conv_id_or_path:
        return None

    # Direct file path
    if os.path.isfile(conv_id_or_path):
        return conv_id_or_path

    # Directory path passed
    if os.path.isdir(conv_id_or_path):
        candidate = os.path.join(conv_id_or_path, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isfile(candidate):
            return candidate
        candidate_flat = os.path.join(conv_id_or_path, "transcript.jsonl")
        if os.path.isfile(candidate_flat):
            return candidate_flat

    # Treat as conversation UUID
    clean_id = conv_id_or_path.strip().strip("'\"")
    candidate = os.path.join(brain_dir, clean_id, ".system_generated", "logs", "transcript.jsonl")
    if os.path.isfile(candidate):
        return candidate

    return None


def get_latest_conversation(brain_dir: str = DEFAULT_BRAIN_DIR) -> Optional[str]:
    """Find the most recently modified conversation in the brain directory."""
    pattern = os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    parts = latest.split(os.sep)
    try:
        # UUID is right before .system_generated
        idx = parts.index(".system_generated")
        return parts[idx - 1]
    except ValueError:
        return None


def search_conversations_by_role(
    role_query: str,
    brain_dir: str = DEFAULT_BRAIN_DIR,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """Search conversations that invoked or acted as a specific subagent role or type."""
    pattern = os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    results = []
    q_lower = role_query.lower()

    for fpath in files:
        parts = fpath.split(os.sep)
        try:
            conv_id = parts[parts.index(".system_generated") - 1]
        except ValueError:
            continue

        matched_roles = set()
        matched_types = set()
        total_tokens = 0
        step_count = 0

        try:
            with open(fpath, "r", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    step = json.loads(line)
                    step_count += 1
                    total_tokens += step.get("input_tokens", 0) + step.get("output_tokens", 0)
                    for tc in step.get("tool_calls", []):
                        if tc.get("name") == "invoke_subagent":
                            args = tc.get("args", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except Exception:
                                    pass
                            if isinstance(args, dict):
                                r = str(args.get("Role", "")).strip("\"'")
                                t = str(args.get("TypeName", "")).strip("\"'")
                                if q_lower in r.lower() or q_lower in t.lower():
                                    matched_roles.add(r)
                                    matched_types.add(t)
        except Exception:
            continue

        if matched_roles or matched_types:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
            results.append({
                "conversation_id": conv_id,
                "roles": list(matched_roles),
                "types": list(matched_types),
                "steps": step_count,
                "total_tokens": total_tokens,
                "modified_at": mtime
            })
            if len(results) >= limit:
                break

    return results


def parse_raw_transcript(transcript_path: str) -> List[Dict[str, Any]]:
    """Load and parse JSONL steps from a transcript file."""
    steps = []
    if not os.path.isfile(transcript_path):
        return steps

    with open(transcript_path, "r", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                steps.append(json.loads(line))
            except Exception:
                continue
    return steps


def extract_subagent_conversations(
    steps: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extract all invoke_subagent tool calls and resolve their returned conversationId."""
    invocations = []
    uuid_patterns = [
        re.compile(r'["\']conversationId["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', re.IGNORECASE),
        re.compile(r'conversationId["\':\s=]+([a-f0-9\-]{36})', re.IGNORECASE),
        re.compile(r'["\']subagentId["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', re.IGNORECASE),
        re.compile(r'["\']recipient["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', re.IGNORECASE),
        re.compile(r'\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b', re.IGNORECASE)
    ]

    for i, step in enumerate(steps):
        for tc in step.get("tool_calls", []):
            if tc.get("name") != "invoke_subagent":
                continue

            args = tc.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass

            role = ""
            type_name = ""
            model = ""
            if isinstance(args, dict):
                role = str(args.get("Role", "")).strip("\"'")
                type_name = str(args.get("TypeName", "")).strip("\"'")
                model = str(args.get("Model", "")).strip("\"'")

            # Search following steps (up to 8 steps ahead) for conversationId in output
            sub_id = None
            for nxt in steps[i + 1:min(i + 8, len(steps))]:
                content = str(nxt.get("content", ""))
                for pat in uuid_patterns:
                    m = pat.search(content)
                    if m:
                        sub_id = m.group(1)
                        break
                if sub_id:
                    break

            invocations.append({
                "step_index": step.get("step_index", i),
                "role": role,
                "type_name": type_name,
                "model": model,
                "conversation_id": sub_id,
                "created_at": step.get("created_at")
            })

    return invocations


def parse_agent_tree(
    conv_id: str,
    brain_dir: str = DEFAULT_BRAIN_DIR,
    visited_ids: Optional[Set[str]] = None,
    depth: int = 0
) -> Dict[str, Any]:
    """Recursively parse an agent conversation and all child subagents into a hierarchical tree."""
    if visited_ids is None:
        visited_ids = set()

    node: Dict[str, Any] = {
        "conversation_id": conv_id,
        "depth": depth,
        "steps_count": 0,
        "input_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "start_time": None,
        "end_time": None,
        "tool_counts": {},
        "commands": [],
        "steps": [],
        "children": [],
        "error": None
    }

    if conv_id in visited_ids:
        node["error"] = "Circular reference detected"
        return node
    visited_ids.add(conv_id)

    transcript_path = resolve_conversation_path(conv_id, brain_dir)
    if not transcript_path:
        node["error"] = f"Transcript not found for {conv_id}"
        return node

    steps = parse_raw_transcript(transcript_path)
    node["steps_count"] = len(steps)

    if not steps:
        return node

    node["start_time"] = steps[0].get("created_at")
    node["end_time"] = steps[-1].get("created_at")

    total_in = 0
    total_cache = 0
    total_out = 0
    tool_counts: Dict[str, int] = {}
    commands: List[str] = []

    for step in steps:
        inp = step.get("input_tokens", 0) or 0
        cache = step.get("cache_read_tokens", 0) or 0
        out = step.get("output_tokens", 0) or 0
        total_in += inp
        total_cache += cache
        total_out += out

        # Turn timeline summary
        tool_names = []
        for tc in step.get("tool_calls", []):
            name = tc.get("name", "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1
            tool_names.append(name)
            args = tc.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if name == "run_command" and isinstance(args, dict):
                cmd = args.get("CommandLine")
                if cmd:
                    commands.append(cmd)

        if inp > 0 or out > 0 or tool_names:
            node["steps"].append({
                "step_index": step.get("step_index"),
                "type": step.get("type"),
                "created_at": step.get("created_at"),
                "input_tokens": inp,
                "cache_read_tokens": cache,
                "output_tokens": out,
                "tools": tool_names
            })

    node["input_tokens"] = total_in
    node["cache_read_tokens"] = total_cache
    node["output_tokens"] = total_out
    node["tool_counts"] = tool_counts
    node["commands"] = commands

    # Discover and recursively parse child subagents
    sub_invocations = extract_subagent_conversations(steps)
    for inv in sub_invocations:
        child_id = inv.get("conversation_id")
        if child_id:
            child_tree = parse_agent_tree(
                conv_id=child_id,
                brain_dir=brain_dir,
                visited_ids=visited_ids,
                depth=depth + 1
            )
            child_tree["role"] = inv.get("role")
            child_tree["type_name"] = inv.get("type_name")
            child_tree["model"] = inv.get("model")
            child_tree["invoked_at_step"] = inv.get("step_index")
            node["children"].append(child_tree)

    return node
