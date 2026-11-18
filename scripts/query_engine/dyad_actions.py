"""CLI action handlers for Interlocutor Dyad and Entity Pre-Mapping tools."""

import sqlite3
import sys
from typing import Dict, Any, Optional

from .interlocutor_dyad import (
    build_interlocutor_grounding_card,
    build_dyad_episodes_map,
    print_interlocutor_grounding_report,
    print_dyad_episodes_report,
)
from .entity_profile_decider import (
    map_entity_profile_system1,
    print_entity_profile_map_report,
)


def handle_dyad_and_profile_actions(
    args: Any,
    batch_config: Dict[str, Any],
    resolved_chat_id: Optional[str]
) -> bool:
    """Handle CLI dispatch for --interlocutor-grounding, --dyad-episodes, and --entity-profile-map."""
    do_grounding = getattr(args, "interlocutor_grounding", False) or batch_config.get("interlocutor_grounding", False)
    do_dyad_episodes = getattr(args, "dyad_episodes", False) or batch_config.get("dyad_episodes", False)
    entity_map_target = getattr(args, "entity_profile_map", None) or batch_config.get("entity_profile_map")

    if not do_grounding and not do_dyad_episodes and not entity_map_target:
        return False

    if not resolved_chat_id:
        print("[!] Error: A valid chat ID (-C <chat_id>) is required.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(args.db)

    try:
        if do_grounding:
            print(f"[*] Extracting System-1 Interlocutor Biographical Grounding for chat '{resolved_chat_id}'...")
            card = build_interlocutor_grounding_card(conn, resolved_chat_id)
            print_interlocutor_grounding_report(card)

        if do_dyad_episodes:
            print(f"[*] Extracting System-1 Dyadic Interaction Episodes for chat '{resolved_chat_id}'...")
            episodes = build_dyad_episodes_map(conn, resolved_chat_id)
            print_dyad_episodes_report(episodes, resolved_chat_id)

        if entity_map_target:
            batch_size = getattr(args, "batch_size", 4) or 4
            print(f"[*] Pre-mapping threads & extracting facts for entity '{entity_map_target}' via System-1...")
            profile_map = map_entity_profile_system1(conn, resolved_chat_id, entity_map_target, batch_size=batch_size)
            print_entity_profile_map_report(profile_map)

    finally:
        conn.close()

    return True
