"""CLI argument parser construction for query_chat."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build and return argparse.ArgumentParser for query_chat."""
    parser = argparse.ArgumentParser(
        description="Query Telegram analytical SQLite and vector database (multi-chat support)."
    )
    parser.add_argument("--db", default="chat.db", help="Path to analytical SQLite database (default: chat.db)")
    parser.add_argument("--chat", "-C", type=str, help="Filter query to a specific chat by chat_id or chat_name")
    parser.add_argument("--list-chats", action="store_true", help="Display catalog of all indexed chats in the database")

    # Analytical flags
    parser.add_argument("--stats", action="store_true", help="Display Phase 1 quantitative metrics")
    parser.add_argument("--gaps", action="store_true", help="Display silence and reconnection initiative analysis across duration brackets")
    parser.add_argument("--min-hours", type=float, default=24.0, help="Minimum silence duration in hours (default: 24)")
    parser.add_argument("--min-days", type=float, help="Minimum silence duration in days (convenience alias for --min-hours = days * 24)")
    parser.add_argument("--timeline", action="store_true", help="Display monthly activity timeline")
    parser.add_argument("--burning-days", action="store_true", help="Display statistically anomalous high-activity days (burning days)")
    parser.add_argument("--intensive-threads", action="store_true", help="Display substantive dialogue threads ranked by volume (anti-noise)")
    parser.add_argument("--min-words", type=int, default=50, help="Minimum total words for --intensive-threads (default: 50)")
    parser.add_argument("--min-messages", type=int, default=6, help="Minimum messages for --intensive-threads (default: 6)")
    parser.add_argument("--triaged-threads", action="store_true", help="Display threads qualified by System-1 (Jev) triage for LLM profiling")
    parser.add_argument("--anomalies-only", action="store_true", help="Display only triaged threads with atypical behavior or interlocutor surprise")
    parser.add_argument("--emotional-peaks", action="store_true", help="Display only triaged threads with acute emotional peaks")
    parser.add_argument("--peak-type", type=str, help="Filter --emotional-peaks by type (profound_sadness, euphoric_joy, intense_rage)")
    parser.add_argument("--advice-seeking", action="store_true", help="Display only triaged threads with intimate confessions or advice seeking")
    parser.add_argument("--min-salience", type=float, default=0.0, help="Minimum salience score for --triaged-threads")
    parser.add_argument("--triage-category", type=str, help="Filter --triaged-threads by primary category")
    parser.add_argument("--triage-status", action="store_true", help="Display summary reduction report of System-1 triage")

    # Repeatable flags for multi-query execution
    parser.add_argument("--search", "-s", action="append", help="Search individual messages via FTS5 (can be repeated)")
    parser.add_argument("--sender", "-S", type=str, help="Filter message search (-s) by sender name or alias")
    parser.add_argument("--search-threads", "-st", action="append", help="Search full dialogue threads via FTS5 (can be repeated)")
    parser.add_argument("--thread", "-t", action="append", help="Display full transcript of a thread by thread_id or message_id (can be repeated)")
    parser.add_argument("--summary-only", "-so", action="store_true", help="Display only thread header, summary, and candidate entities without full message transcripts for -t")
    parser.add_argument("--thread-snippets", "-ts", action="append", help="Display windowed context snippets (±window msgs, default 4) around candidate entity mentions in a thread (can be repeated)")
    parser.add_argument("--mentions", action="append", help="Explicit mention names to search snippets for in --thread-snippets (can be repeated)")
    parser.add_argument("--msg", "-m", action="append", type=int, help="Inspect a specific message by message_id with pagination (can be repeated)")
    parser.add_argument("--part", type=int, default=1, help="Part/page number to display for long messages (default: 1)")
    parser.add_argument("--part-size", type=int, default=1500, help="Character size per part for --msg (default: 1500)")
    parser.add_argument("--all", action="store_true", help="Display entire message text without truncation or pagination")
    parser.add_argument("--from-msg", "-f", action="append", type=int, help="Display a slice of a thread starting from this message_id (can be repeated)")
    parser.add_argument("--window", "-w", type=int, default=0, help="Number of preceding messages to show before --from-msg (default: 0)")
    parser.add_argument("--chain", "-c", action="append", type=int, help="Display direct causal quote chain for a message_id (can be repeated)")
    parser.add_argument("--around", "-ar", "-ctx", action="append", type=int, help="Display chronological context surrounding a message across thread boundaries (can be repeated)")
    parser.add_argument("--semantic", "-sem", action="append", help="Search threads by psychological concept/meaning (can be repeated)")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Maximum number of results to display per query (default: 10)")

    # Agent productivity features
    parser.add_argument("--json", action="store_true", help="Output all results in structured JSON format")
    parser.add_argument("--batch-json", type=str, help="JSON string or file path containing multiple query directives")
    parser.add_argument("--checklist", action="store_true", help="Display life spheres investigation checklist status")
    parser.add_argument("--waive-checklist", action="store_true", help="Waive/disable life spheres checklist for ad-hoc / partial tasks")
    parser.add_argument("--threads-checklist", action="store_true", help="Display thread audit checklist status (Track B - Substantive threads)")
    parser.add_argument("--next-thread", action="store_true", help="Display next pending thread waiting for audit in thread checklist")
    parser.add_argument("--waive-threads-checklist", action="store_true", help="Waive/disable thread audit checklist for ad-hoc / partial tasks")
    parser.add_argument("--reason", type=str, default="Ad-hoc task / partial inquiry (full profiling not required)", help="Reason for waiving checklist")

    # Entity Disambiguation & Descriptor Registry flags
    parser.add_argument("--entities", action="store_true", help="Display catalog of registered third-party entities for the selected chat")
    parser.add_argument("--descriptors", action="store_true", help="Display catalog of audited role/geographic descriptors and their cardinality")
    parser.add_argument("--audit-descriptor", type=str, help="Run lazy cardinality audit on a descriptor (e.g. 'sister', 'US guy')")
    parser.add_argument("--register-entity", type=str, help="Register or update a third-party entity (provide name/alias)")
    parser.add_argument("--role", type=str, help="Verified role for --register-entity (e.g. 'ex-partner', 'platonic friend')")
    parser.add_argument("--desc", type=str, help="Associated descriptors/notes for --register-entity")
    parser.add_argument("--ex", action="store_true", help="Mark entity as ex-partner in --register-entity")
    parser.add_argument("--romantic", action="store_true", help="Mark entity as romantic prospect/partner in --register-entity")
    parser.add_argument("--non-romantic", action="store_true", help="Explicitly mark entity as non-romantic in --register-entity")
    parser.add_argument("--first-msg", type=int, help="First message ID introducing the entity")
    parser.add_argument("--confidence", type=str, default="verified", help="Confidence status for entity ('verified', 'unverified', 'hypothetical')")
    parser.add_argument("--watchdog-check", type=str, help="Run adversarial System-1 watchdog on a thread_id against registered entities")
    parser.add_argument("--known", action="append", help="Explicit list of known entities for --watchdog-check (can be repeated)")
    parser.add_argument("--anomaly-check", type=str, help="Run adversarial System-1 check on a thread_id to detect whether secondary/unaddressed anomalies remain")
    parser.add_argument("--identified", action="append", help="Already identified/accounted anomalies for --anomaly-check (can be repeated)")
    parser.add_argument("--watchdog-scan", action="store_true", help="Run sequential System-1 watchdog scan on third-party threads")
    parser.add_argument("--sweep", action="store_true", help="Run watchdog scan in full non-blocking sweep mode across all remaining threads")
    parser.add_argument("--candidates", "--candidate-entities", action="store_true", help="Display extracted candidate entities from thread triage for multi-agent clustering")
    parser.add_argument("--conflation-audit", action="store_true", help="Run immediate anti-conflation and collision audit across registered entities")
    parser.add_argument("--watchdog-status", action="store_true", help="Display summary progress of sequential entity watchdog scan")
    parser.add_argument("--skip-thread", type=str, help="Mark thread as skipped/false-positive in entity scan to resume progress")
    parser.add_argument("--reset-watchdog-scan", action="store_true", help="Reset watchdog scan progress for the target chat")
    parser.add_argument("--check-watchdog-gate", action="store_true", help="Run hard-stop gatekeeper check for Entity Watchdog (exit 0 on pass, exit 1 on fail)")

    return parser
