"""Display and formatting views for Life Spheres Checklist."""

from typing import List, Dict, Any


def print_status_summary(stats: Dict[str, Any]):
    """Print a clean human-readable dashboard of checklist progress and semantic vector coverage."""
    print("=" * 72)
    print(f"📋 LIFE SPHERES INVESTIGATION CHECKLIST: Chat '{stats['chat_id']}'")
    if stats.get("is_waived"):
        print("  ⚠️  CHECKLIST STATUS: WAIVED / EXEMPT")
        print(f"  Reason: {stats.get('waiver_reason')}")
        print("  (Sub-items are not required for this ad-hoc / partial task)")
    print("=" * 72)
    bar_len = 30
    filled = int(round(bar_len * stats["percent"] / 100.0))
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"Resolution Progress: [{bar}] {stats['percent']:.1f}% ({stats['resolved']}/{stats['total']} resolved)")
    print(f"  ✓ Completed (Evidence Found):   {stats['completed']}")
    print(f"  ∅ No Data (Probed & Absent):    {stats['no_data']}")
    print(f"  ⊘ Not Applicable / Waived:      {stats['not_applicable']}")
    print(f"  ⏳ Pending Audit:                {stats['pending']}")
    print("-" * 72)
    substantive = stats["completed"] + stats["no_data"]
    sem_pct = stats.get("semantic_coverage_pct", 0.0)
    sem_filled = int(round(bar_len * sem_pct / 100.0))
    sem_bar = "█" * sem_filled + "░" * (bar_len - sem_filled)
    print(f"🧠 Semantic Vector Probes: [{sem_bar}] {sem_pct:.1f}% ({stats.get('semantic_probed', 0)}/{substantive} substantive items probed)")
    print("-" * 72)
    print("Spheres Breakdown:")
    for s in stats["spheres"]:
        s_bar_len = 16
        s_filled = int(round(s_bar_len * s["percent"] / 100.0))
        s_bar = "█" * s_filled + "░" * (s_bar_len - s_filled)
        print(f"  [{s['sphere_id']}] {s['sphere_name'][:36]:<36} [{s_bar}] {s['percent']:>5.1f}%  (Pending: {s['pending']})")
    print("=" * 72)


def print_items_list(items: List[Dict[str, Any]], detailed: bool = False):
    """Print a list of checklist items with their statuses."""
    if not items:
        print("[*] No checklist items found matching criteria.")
        return

    status_icons = {
        "completed": "✓",
        "no_data": "∅",
        "not_applicable": "⊘",
        "pending": "⏳"
    }

    print("=" * 80)
    print(f"📋 LIFE SPHERES CHECKLIST ITEMS ({len(items)} items)")
    print("=" * 80)
    for it in items:
        icon = status_icons.get(it["status"], "?")
        print(f"[{icon}] [{it['sphere_id']}] {it['item_id']:<38} [{it['status'].upper():<14}] {it['sub_item']}")
        if detailed:
            print(f"    Description: {it['description']}")
            if it["evidence_summary"]:
                print(f"    Evidence:    {it['evidence_summary']}")
            if it["query_terms_used"]:
                print(f"    Queries:     {it['query_terms_used']}")
            if it["semantic_queries_used"]:
                print(f"    Semantic:    {it['semantic_queries_used']}")
            print(f"    Updated:     {it['updated_at']}")
            print("-" * 80)
    if not detailed:
        print("=" * 80)
