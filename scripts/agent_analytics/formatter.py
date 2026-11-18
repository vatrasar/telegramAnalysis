"""Presentation and formatting module for agent token analytics."""

import json
from typing import Dict, Any, List


def format_tokens(n: int) -> str:
    """Format token count with thousands separators or K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}k"
    return f"{n:,}"


def render_ascii_tree(tree: Dict[str, Any], prefix: str = "", is_last: bool = True) -> str:
    """Recursively render hierarchical tree of agent and subagents."""
    lines = []
    connector = "└── " if is_last else "├── "
    child_prefix = prefix + ("    " if is_last else "│   ")

    depth = tree.get("depth", 0)
    role = tree.get("role") or tree.get("type_name") or ("Root Agent" if depth == 0 else "Subagent")
    conv_id = tree.get("conversation_id", "")[:8]
    loc = tree.get("local_metrics", {})
    cost_usd = loc.get("cost_usd", 0.0)
    duration_str = loc.get("duration_formatted", "0s")

    icon = "👑" if depth == 0 else ("👥" if tree.get("children") else "🔍")
    node_str = (
        f"{icon} {role} [{conv_id}] | "
        f"In: {format_tokens(loc.get('input_tokens', 0))}, "
        f"Cache: {format_tokens(loc.get('cache_read_tokens', 0))}, "
        f"Out: {format_tokens(loc.get('output_tokens', 0))} | "
        f"${cost_usd:.4f} | {duration_str}"
    )

    if depth == 0:
        lines.append(node_str)
    else:
        lines.append(f"{prefix}{connector}{node_str}")

    children = tree.get("children", [])
    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        sub_text = render_ascii_tree(child, "" if depth == 0 else child_prefix, is_child_last)
        lines.append(sub_text)

    return "\n".join(lines)


def render_summary_card(tree: Dict[str, Any]) -> str:
    """Render executive summary card of total token consumption and costs."""
    agg = tree.get("aggregate_metrics", {})
    loc = tree.get("local_metrics", {})

    lines = [
        "=" * 84,
        f"📊 AGENT TOKEN & LATENCY ANALYTICS REPORT: {tree.get('conversation_id')}",
        "=" * 84,
        f"Execution Scope:  {'Root + Subagent Tree' if tree.get('children') else 'Single Agent'}",
        f"Wall-Clock Time:  {agg.get('tree_wall_clock_formatted', '0s')} ({agg.get('tree_wall_clock_seconds', 0)}s)",
        f"Active Work Time: {agg.get('tree_active_duration_formatted', '0s')} (Sum of all agents in parallel)",
        f"Subagents Spawned: {agg.get('total_subagents', 0)}",
        "-" * 84,
        "TOKEN CONSUMPTION MATRIX:",
        f"  • Raw Input Tokens:      {agg.get('tree_input_tokens', 0):>12,}  ({format_tokens(agg.get('tree_input_tokens', 0))})",
        f"  • Cache Read Tokens:     {agg.get('tree_cache_read_tokens', 0):>12,}  ({format_tokens(agg.get('tree_cache_read_tokens', 0))})",
        f"  • Generated Output:      {agg.get('tree_output_tokens', 0):>12,}  ({format_tokens(agg.get('tree_output_tokens', 0))})",
        f"  • Billable Tokens:       {agg.get('tree_billable_tokens', 0):>12,}  (Input + Output)",
        f"  • Total Processed:       {agg.get('tree_total_tokens', 0):>12,}  (Input + Cache + Output)",
        f"  • Cache Hit Rate:        {agg.get('tree_cache_hit_rate', 0.0):>11.1f}%",
        f"  • Estimated Cost (USD):  ${agg.get('tree_cost_usd', 0.0):>11.4f}",
        "-" * 84,
    ]

    # Velocity and surge metrics
    vel = agg.get("velocity", {})
    if vel and vel.get("peak_minute"):
        lines.append("CONCURRENCY & VELOCITY METRICS:")
        lines.append(f"  • Avg Token Velocity:    {format_tokens(vel.get('avg_tokens_per_min', 0)):>12}/min (across active minutes)")
        lines.append(f"  • Peak Velocity Rate:    {format_tokens(vel.get('peak_tokens_per_min', 0)):>12}/min (at {vel.get('peak_minute')} | {vel.get('peak_active_agents')} active agents)")
        if vel.get("surge_detected"):
            lines.append(f"  • 🔥 SURGE MULTIPLIER:   {vel.get('surge_factor', 1.0):>11.1f}× baseline  [⚠️ HIGH TOKEN SURGE DETECTED]")
        else:
            lines.append(f"  • Surge Multiplier:      {vel.get('surge_factor', 1.0):>11.1f}× baseline  (Normal)")
        lines.append("-" * 84)

    # Tool calls table
    tools = agg.get("all_tool_counts", {})
    if tools:
        lines.append("TOOL CALLS BREAKDOWN:")
        for tool, count in sorted(tools.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  • {tool:<28} {count:>5} calls")
        lines.append("-" * 84)

    # Subagents by role
    sub_roles = agg.get("subagents_by_role", {})
    if sub_roles:
        lines.append("SUBAGENTS BY ROLE BREAKDOWN:")
        lines.append(f"  {'Role / Type':<32} {'Count':<6} {'In Tok':<9} {'Cache Tok':<10} {'Total Proc':<11} {'Out Tok':<9} {'Cost ($)':<9}")
        lines.append("  " + "-" * 90)
        for role, sdata in sorted(sub_roles.items(), key=lambda x: x[1].get("cache_tokens", 0) + x[1].get("input_tokens", 0), reverse=True):
            r_trunc = role[:30]
            inp = sdata.get('input_tokens', 0)
            cache = sdata.get('cache_tokens', 0)
            out = sdata.get('output_tokens', 0)
            total = inp + cache + out
            lines.append(
                f"  {r_trunc:<32} {sdata['count']:<6} {format_tokens(inp):<9} "
                f"{format_tokens(cache):<10} {format_tokens(total):<11} "
                f"{format_tokens(out):<9} ${sdata['cost_usd']:<8.4f}"
            )
        lines.append("-" * 84)

    # Top commands
    top_cmds = agg.get("top_commands", [])
    if top_cmds:
        lines.append("TOP EXECUTED COMMANDS:")
        for cmd, count in top_cmds[:7]:
            lines.append(f"  [{count:>2}x] {cmd}")
        lines.append("-" * 84)

    lines.append("=" * 84)
    return "\n".join(lines)


def render_timeline(tree: Dict[str, Any], limit: int = 40) -> str:
    """Render turn-by-turn timeline table for the agent."""
    steps = tree.get("steps", [])
    if not steps:
        return "No steps recorded."

    lines = [
        f"\n⏱️  TURN-BY-TURN TIMELINE (Showing last {min(limit, len(steps))} of {len(steps)} steps):",
        f"{'Step':<6} {'Type':<18} {'Input':<10} {'Cache':<10} {'Output':<10} {'Tools Called'}",
        "-" * 84
    ]

    for s in steps[-limit:]:
        tools_str = ", ".join(s.get("tools", [])) or "-"
        lines.append(
            f"{s.get('step_index', 0):<6} "
            f"{str(s.get('type', '')):<18} "
            f"{format_tokens(s.get('input_tokens', 0)):<10} "
            f"{format_tokens(s.get('cache_read_tokens', 0)):<10} "
            f"{format_tokens(s.get('output_tokens', 0)):<10} "
            f"{tools_str[:30]}"
        )

    return "\n".join(lines)


def generate_markdown_report(tree: Dict[str, Any]) -> str:
    """Generate structured Markdown report suitable for persistence or user presentation."""
    agg = tree.get("aggregate_metrics", {})
    tree_ascii = render_ascii_tree(tree)

    md = [
        f"# Agent Token & Latency Profile: `{tree.get('conversation_id')}`",
        "",
        "## Executive Summary",
        "",
        "| Metric | Total (Tree) | Local (Root) |",
        "| :--- | :--- | :--- |",
        f"| **Billable Tokens** | **{agg.get('tree_billable_tokens', 0):,}** | {tree.get('local_metrics', {}).get('billable_tokens', 0):,} |",
        f"| **Input Tokens** | {agg.get('tree_input_tokens', 0):,} | {tree.get('local_metrics', {}).get('input_tokens', 0):,} |",
        f"| **Cache Read Tokens** | {agg.get('tree_cache_read_tokens', 0):,} | {tree.get('local_metrics', {}).get('cache_read_tokens', 0):,} |",
        f"| **Output Tokens** | {agg.get('tree_output_tokens', 0):,} | {tree.get('local_metrics', {}).get('output_tokens', 0):,} |",
        f"| **Cache Hit Ratio** | {agg.get('tree_cache_hit_rate', 0.0):.1f}% | {tree.get('local_metrics', {}).get('cache_hit_rate', 0.0):.1f}% |",
        f"| **Estimated Cost** | **${agg.get('tree_cost_usd', 0.0):.4f}** | ${tree.get('local_metrics', {}).get('cost_usd', 0.0):.4f} |",
        f"| **Wall-Clock Duration** | {agg.get('tree_wall_clock_formatted', '0s')} | {tree.get('local_metrics', {}).get('duration_formatted', '0s')} |",
        f"| **Subagents Spawned** | {agg.get('total_subagents', 0)} | - |",
        "",
        "## Agent Hierarchy Tree",
        "",
        "```text",
        tree_ascii,
        "```",
        ""
    ]

    sub_roles = agg.get("subagents_by_role", {})
    if sub_roles:
        md.extend([
            "## Subagent Invocations by Role",
            "",
            "| Subagent Role | Invocations | Input Tokens | Cache Read | Total Processed | Output Tokens | Cost ($) | Duration |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ])
        for role, sdata in sorted(sub_roles.items(), key=lambda x: x[1].get("cache_tokens", 0) + x[1].get("input_tokens", 0), reverse=True):
            inp = sdata.get('input_tokens', 0)
            cache = sdata.get('cache_tokens', 0)
            out = sdata.get('output_tokens', 0)
            tot = inp + cache + out
            md.append(
                f"| `{role}` | {sdata['count']} | {inp:,} | {cache:,} | **{tot:,}** | "
                f"{out:,} | ${sdata['cost_usd']:.4f} | {int(sdata['duration_seconds'])}s |"
            )
        md.append("")

    return "\n".join(md)


def render_velocity_timeline(tree: Dict[str, Any], limit: int = 40) -> str:
    """Render minute-by-minute token velocity and concurrency timeline."""
    agg = tree.get("aggregate_metrics", {})
    vel = agg.get("velocity", {})
    buckets = vel.get("minute_buckets", [])
    if not buckets:
        return "No velocity timeline data recorded."

    lines = [
        "=" * 92,
        "⏱️  MINUTE-BY-MINUTE TOKEN VELOCITY & CONCURRENCY TIMELINE",
        "=" * 92,
        f"{'Minute':<17} {'Agents':<8} {'Input Tok':<11} {'Cache Read':<12} {'Output Tok':<11} {'TOTAL PROCESSED':<16} {'Rate Flag'}",
        "-" * 92
    ]

    baseline = max(10_000, vel.get("avg_tokens_per_min", 0))

    for b in buckets[-limit:]:
        tot = b["total_processed"]
        ratio = tot / baseline if baseline > 0 else 1.0
        flag = ""
        if tot >= 10_000_000 or ratio >= 20.0:
            flag = "[🔥 SEVERE SURGE]"
        elif tot >= 2_000_000 or ratio >= 5.0:
            flag = "[⚠️ HIGH VELOCITY]"
        elif tot >= 500_000:
            flag = "[ELEVATED]"
        else:
            flag = "[NORMAL]"

        lines.append(
            f"{b['minute']:<17} {b['active_agents']:<8} "
            f"{format_tokens(b['input_tokens']):<11} "
            f"{format_tokens(b['cache_read_tokens']):<12} "
            f"{format_tokens(b['output_tokens']):<11} "
            f"{format_tokens(tot):<16} "
            f"{flag}"
        )

    lines.append("=" * 92)
    return "\n".join(lines)
