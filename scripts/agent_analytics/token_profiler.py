"""Token calculation, cost estimation, duration analysis, and tree aggregation."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Standard Pricing per Million Tokens ($ / 1M tokens)
# Configurable based on standard Gemini & OpenRouter model tiers
DEFAULT_PRICING = {
    "flash": {
        "input_per_m": 0.075,
        "cache_per_m": 0.01875,
        "output_per_m": 0.30
    },
    "flash_lite": {
        "input_per_m": 0.0375,
        "cache_per_m": 0.01,
        "output_per_m": 0.15
    },
    "pro": {
        "input_per_m": 1.25,
        "cache_per_m": 0.3125,
        "output_per_m": 5.00
    },
    "default": {
        "input_per_m": 0.075,
        "cache_per_m": 0.01875,
        "output_per_m": 0.30
    }
}


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime strings safely."""
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


def calculate_cost(
    input_tokens: int,
    cache_tokens: int,
    output_tokens: int,
    model_name: Optional[str] = None
) -> float:
    """Calculate estimated dollar cost given token counts and model pricing."""
    pricing = DEFAULT_PRICING.get("default")
    if model_name:
        m_lower = model_name.lower()
        if "lite" in m_lower:
            pricing = DEFAULT_PRICING.get("flash_lite", pricing)
        elif "pro" in m_lower:
            pricing = DEFAULT_PRICING.get("pro", pricing)
        elif "flash" in m_lower:
            pricing = DEFAULT_PRICING.get("flash", pricing)

    cost_in = (input_tokens / 1_000_000.0) * pricing["input_per_m"]
    cost_cache = (cache_tokens / 1_000_000.0) * pricing["cache_per_m"]
    cost_out = (output_tokens / 1_000_000.0) * pricing["output_per_m"]
    return cost_in + cost_cache + cost_out


def calculate_duration_seconds(
    start_str: Optional[str],
    end_str: Optional[str]
) -> float:
    """Calculate elapsed duration in seconds between two ISO timestamps."""
    start_dt = parse_iso_datetime(start_str)
    end_dt = parse_iso_datetime(end_str)
    if start_dt and end_dt:
        diff = (end_dt - start_dt).total_seconds()
        return max(0.0, diff)
    return 0.0


def format_duration(seconds: float) -> str:
    """Format duration into readable minutes and seconds string."""
    if seconds <= 0:
        return "0s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def compute_node_metrics(
    node: Dict[str, Any],
    cost_model: Optional[str] = None
) -> Dict[str, Any]:
    """Compute local metrics for a single node (agent or subagent) without children."""
    inp = node.get("input_tokens", 0)
    cache = node.get("cache_read_tokens", 0)
    out = node.get("output_tokens", 0)
    billable = inp + out
    total = inp + cache + out

    denom = (inp + cache)
    cache_hit_rate = (cache / denom * 100.0) if denom > 0 else 0.0

    model = node.get("model") or cost_model or "flash"
    cost = calculate_cost(inp, cache, out, model)
    duration = calculate_duration_seconds(node.get("start_time"), node.get("end_time"))

    return {
        "input_tokens": inp,
        "cache_read_tokens": cache,
        "output_tokens": out,
        "billable_tokens": billable,
        "total_tokens": total,
        "cache_hit_rate": round(cache_hit_rate, 2),
        "cost_usd": round(cost, 4),
        "duration_seconds": round(duration, 1),
        "duration_formatted": format_duration(duration),
        "steps_count": node.get("steps_count", 0),
        "tool_counts": node.get("tool_counts", {})
    }


def aggregate_tree_profile(
    tree: Dict[str, Any],
    cost_model: Optional[str] = None
) -> Dict[str, Any]:
    """Recursively aggregate metrics across the full agent/subagent tree."""
    local_metrics = compute_node_metrics(tree, cost_model)
    tree["local_metrics"] = local_metrics

    tree_in = local_metrics["input_tokens"]
    tree_cache = local_metrics["cache_read_tokens"]
    tree_out = local_metrics["output_tokens"]
    tree_cost = local_metrics["cost_usd"]
    tree_active_duration = local_metrics["duration_seconds"]
    subagent_count = 0
    all_commands: List[str] = list(tree.get("commands", []))

    all_tool_counts = dict(local_metrics["tool_counts"])
    subagents_by_role: Dict[str, Dict[str, Any]] = {}

    for child in tree.get("children", []):
        subagent_count += 1
        child_agg = aggregate_tree_profile(child, cost_model)

        tree_in += child_agg["tree_input_tokens"]
        tree_cache += child_agg["tree_cache_read_tokens"]
        tree_out += child_agg["tree_output_tokens"]
        tree_cost += child_agg["tree_cost_usd"]
        tree_active_duration += child_agg["tree_active_duration_seconds"]
        all_commands.extend(child.get("commands", []))

        # Merge tool counts
        for tool, count in child_agg["all_tool_counts"].items():
            all_tool_counts[tool] = all_tool_counts.get(tool, 0) + count

        role = child.get("role") or child.get("type_name") or "unspecified"
        if role not in subagents_by_role:
            subagents_by_role[role] = {
                "count": 0,
                "input_tokens": 0,
                "cache_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "duration_seconds": 0.0
            }
        subagents_by_role[role]["count"] += 1
        subagents_by_role[role]["input_tokens"] += child_agg["tree_input_tokens"]
        subagents_by_role[role]["cache_tokens"] += child_agg["tree_cache_read_tokens"]
        subagents_by_role[role]["output_tokens"] += child_agg["tree_output_tokens"]
        subagents_by_role[role]["cost_usd"] += child_agg["tree_cost_usd"]
        subagents_by_role[role]["duration_seconds"] += child_agg["tree_active_duration_seconds"]

    tree_billable = tree_in + tree_out
    tree_total = tree_in + tree_cache + tree_out
    denom = (tree_in + tree_cache)
    tree_cache_rate = (tree_cache / denom * 100.0) if denom > 0 else 0.0

    # Wall-clock duration across entire tree
    tree_wall_clock = calculate_duration_seconds(tree.get("start_time"), tree.get("end_time"))

    # Top command frequencies
    cmd_freq: Dict[str, int] = {}
    for cmd in all_commands:
        base_cmd = cmd.strip().split("\n")[0]
        if len(base_cmd) > 80:
            base_cmd = base_cmd[:77] + "..."
        cmd_freq[base_cmd] = cmd_freq.get(base_cmd, 0) + 1
    top_commands = sorted(cmd_freq.items(), key=lambda x: x[1], reverse=True)[:10]

    aggregated = {
        "tree_input_tokens": tree_in,
        "tree_cache_read_tokens": tree_cache,
        "tree_output_tokens": tree_out,
        "tree_billable_tokens": tree_billable,
        "tree_total_tokens": tree_total,
        "tree_cache_hit_rate": round(tree_cache_rate, 2),
        "tree_cost_usd": round(tree_cost, 4),
        "tree_wall_clock_seconds": round(tree_wall_clock, 1),
        "tree_wall_clock_formatted": format_duration(tree_wall_clock),
        "tree_active_duration_seconds": round(tree_active_duration, 1),
        "tree_active_duration_formatted": format_duration(tree_active_duration),
        "total_subagents": subagent_count,
        "all_tool_counts": all_tool_counts,
        "top_commands": top_commands,
        "subagents_by_role": subagents_by_role
    }

    tree["aggregate_metrics"] = aggregated
    return aggregated
