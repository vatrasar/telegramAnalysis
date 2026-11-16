"""Thread re-read and cross-agent redundancy analyzer with multi-tier inspection depth classification."""

import re
from typing import Dict, Any, List, Tuple, Set, Optional

# Regex matching various ways threads are referenced in query_chat commands
THREAD_ARG_REGEX = re.compile(
    r'(?:-t|--thread|--thread-snippets|--watchdog-check|--skip-thread|--inspect-thread|--mark-inspected)\s+([a-zA-Z0-9_\-]+)'
)


def classify_read_type(cmd: str) -> str:
    """Classify inspection depth into FULL (entire transcript), PARTIAL (snippets/windows), or METADATA (summaries/status)."""
    cmd_lower = cmd.lower()

    # Metadata / summary queries (zero or minimal transcript dialogue)
    if any(k in cmd_lower for k in ["--summary-only", "--watchdog-check", "--skip-thread", "--mark-inspected", "--watchdog-status"]):
        return "METADATA"

    # Partial / snippet queries (only focused 5-10 message windows or snippets)
    if any(k in cmd_lower for k in ["--thread-snippets", "--inspect-context", "-w ", "--window "]):
        return "PARTIAL"

    # Full dialogue text dump (-t or --thread)
    if " -t " in cmd or " --thread " in cmd or " -t\n" in cmd:
        return "FULL"

    return "PARTIAL"


def extract_all_commands(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursively collect all commands executed across coordinator and subagents."""
    commands = []
    conv_id = tree.get("conversation_id", "")
    role = tree.get("role") or tree.get("type_name") or ("Root Agent" if tree.get("depth", 0) == 0 else "Subagent")

    for cmd in tree.get("commands", []):
        commands.append({
            "conversation_id": conv_id,
            "role": role,
            "depth": tree.get("depth", 0),
            "command": cmd
        })

    for child in tree.get("children", []):
        commands.extend(extract_all_commands(child))

    return commands


def analyze_thread_redundancy(tree: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze thread inspection frequency, categorizing by FULL, PARTIAL, and METADATA tiers."""
    commands = extract_all_commands(tree)

    thread_accesses: Dict[str, List[Dict[str, Any]]] = {}
    agent_thread_map: Dict[str, Set[str]] = {}

    total_full = 0
    total_partial = 0
    total_metadata = 0

    for item in commands:
        cmd = item["command"]
        role = item["role"]
        conv_id = item["conversation_id"]

        raw_matches = THREAD_ARG_REGEX.findall(cmd)
        matches = [tid for tid in raw_matches if not tid.startswith("-") and len(tid) >= 3]
        if not matches:
            continue

        read_type = classify_read_type(cmd)
        if read_type == "FULL":
            total_full += len(matches)
        elif read_type == "PARTIAL":
            total_partial += len(matches)
        else:
            total_metadata += len(matches)

        for tid in matches:
            if tid not in thread_accesses:
                thread_accesses[tid] = []

            thread_accesses[tid].append({
                "conversation_id": conv_id,
                "role": role,
                "read_type": read_type,
                "command": cmd
            })

            if role not in agent_thread_map:
                agent_thread_map[role] = set()
            agent_thread_map[role].add(tid)

    total_reads = sum(len(acc) for acc in thread_accesses.values())
    unique_threads = len(thread_accesses)
    redundancy_ratio = round(total_reads / max(1, unique_threads), 2)

    single_read_count = 0
    multi_read_count = 0
    cross_agent_count = 0
    intra_agent_count = 0

    thread_details: List[Dict[str, Any]] = []

    for tid, accesses in thread_accesses.items():
        total_acc = len(accesses)
        roles_involved: Dict[str, Dict[str, int]] = {}
        agents_involved = set()

        n_full = 0
        n_partial = 0
        n_meta = 0

        for a in accesses:
            r = a["role"]
            rt = a["read_type"]
            agents_involved.add(a["conversation_id"])

            if r not in roles_involved:
                roles_involved[r] = {"FULL": 0, "PARTIAL": 0, "METADATA": 0}
            roles_involved[r][rt] = roles_involved[r].get(rt, 0) + 1

            if rt == "FULL":
                n_full += 1
            elif rt == "PARTIAL":
                n_partial += 1
            else:
                n_meta += 1

        distinct_roles = len(roles_involved)
        distinct_agents = len(agents_involved)

        is_cross_agent = distinct_roles > 1 or distinct_agents > 1
        is_intra_agent = any(sum(counts.values()) > 1 for counts in roles_involved.values())

        if total_acc == 1:
            single_read_count += 1
        else:
            multi_read_count += 1
            if is_cross_agent:
                cross_agent_count += 1
            if is_intra_agent:
                intra_agent_count += 1

        thread_details.append({
            "thread_id": tid,
            "read_count": total_acc,
            "full_reads": n_full,
            "partial_reads": n_partial,
            "metadata_reads": n_meta,
            "distinct_agents_count": distinct_agents,
            "distinct_roles_count": distinct_roles,
            "is_cross_agent": is_cross_agent,
            "is_intra_agent": is_intra_agent,
            "roles_breakdown": roles_involved,
            "redundant_reads": max(0, total_acc - 1)
        })

    # Sort descending by full_reads first, then total read_count
    thread_details.sort(key=lambda x: (x["full_reads"], x["read_count"]), reverse=True)
    total_redundant_operations = sum(t["redundant_reads"] for t in thread_details)

    # Cross-subagent overlap analysis
    agent_overlap_pairs = []
    roles = list(agent_thread_map.keys())
    for i in range(len(roles)):
        for j in range(i + 1, len(roles)):
            r1, r2 = roles[i], roles[j]
            intersection = agent_thread_map[r1].intersection(agent_thread_map[r2])
            if intersection:
                agent_overlap_pairs.append({
                    "role_a": r1,
                    "role_b": r2,
                    "shared_threads_count": len(intersection),
                    "shared_threads": sorted(list(intersection))[:5]
                })

    agent_overlap_pairs.sort(key=lambda x: x["shared_threads_count"], reverse=True)

    return {
        "total_thread_read_commands": total_reads,
        "total_full_reads": total_full,
        "total_partial_reads": total_partial,
        "total_metadata_reads": total_metadata,
        "unique_threads_accessed": unique_threads,
        "redundancy_ratio": redundancy_ratio,
        "single_read_threads": single_read_count,
        "multi_read_threads": multi_read_count,
        "cross_agent_re_read_threads": cross_agent_count,
        "intra_agent_re_read_threads": intra_agent_count,
        "total_redundant_operations": total_redundant_operations,
        "top_re_read_threads": thread_details[:25],
        "agent_overlap_pairs": agent_overlap_pairs[:10]
    }


def render_thread_redundancy_table(metrics: Dict[str, Any]) -> str:
    """Format thread redundancy metrics as an ASCII report table with inspection tiers."""
    lines = [
        "=" * 92,
        "🔄 THREAD RE-READ & REDUNDANCY AUDIT REPORT (WITH INSPECTION TIERS)",
        "=" * 92,
        f"Total Thread Read Commands:   {metrics.get('total_thread_read_commands', 0)}",
        f"  • FULL_READ (Entire text):   {metrics.get('total_full_reads', 0):>4}  (High token impact: 1.5k-10k tokens each)",
        f"  • PARTIAL_READ (Snippets):   {metrics.get('total_partial_reads', 0):>4}  (Low token impact: 200-500 tokens each)",
        f"  • METADATA_READ (Summaries): {metrics.get('total_metadata_reads', 0):>4}  (Near-zero token impact: 50-100 tokens each)",
        f"Unique Threads Accessed:      {metrics.get('unique_threads_accessed', 0)}",
        f"Global Redundancy Ratio:      {metrics.get('redundancy_ratio', 1.0)}x reads per unique thread",
        f"Redundant Operations:         {metrics.get('total_redundant_operations', 0)} avoidable re-reads",
        f"Threads Read Once (Optimal):  {metrics.get('single_read_threads', 0)}",
        f"Threads Re-Read Multiple:     {metrics.get('multi_read_threads', 0)} (Cross-Agent: {metrics.get('cross_agent_re_read_threads', 0)}, Intra-Agent: {metrics.get('intra_agent_re_read_threads', 0)})",
        "-" * 92,
        "TOP RE-READ THREADS (CLASSIFIED BY INSPECTION DEPTH):",
        f"{'Thread ID':<26} {'Total':<6} {'Full':<5} {'Part':<5} {'Meta':<5} {'Accessing Subagents & Details'}",
        "-" * 92
    ]

    for t in metrics.get("top_re_read_threads", [])[:15]:
        tid_trunc = t["thread_id"][:24]
        agent_strs = []
        for r, counts in t["roles_breakdown"].items():
            short_r = r.split(" - ")[-1][:16]
            details = []
            if counts.get("FULL", 0) > 0:
                details.append(f"{counts['FULL']}F")
            if counts.get("PARTIAL", 0) > 0:
                details.append(f"{counts['PARTIAL']}P")
            if counts.get("METADATA", 0) > 0:
                details.append(f"{counts['METADATA']}M")
            agent_strs.append(f"{short_r} ({'+'.join(details)})")

        agents_display = ", ".join(agent_strs)
        lines.append(
            f"{tid_trunc:<26} {t['read_count']:<6} {t['full_reads']:<5} {t['partial_reads']:<5} {t['metadata_reads']:<5} {agents_display[:40]}"
        )

    overlaps = metrics.get("agent_overlap_pairs", [])
    if overlaps:
        lines.append("-" * 92)
        lines.append("CROSS-SUBAGENT THREAD CONTENTION / OVERLAP:")
        lines.append(f"{'Subagent A':<30} {'Subagent B':<30} {'Shared Threads'}")
        lines.append("-" * 92)
        for pair in overlaps[:6]:
            r_a = pair["role_a"].split(" - ")[-1][:28]
            r_b = pair["role_b"].split(" - ")[-1][:28]
            lines.append(f"{r_a:<30} {r_b:<30} {pair['shared_threads_count']:>5} threads")

    lines.append("=" * 92)
    return "\n".join(lines)
