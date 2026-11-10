#!/usr/bin/env python3
"""
Life Spheres Forensic Checklist & Verification Manager.
Tracks, audits, and enforces complete evidentiary coverage of foundational life spheres
(Social Matrix, Work & Ambitions, Worldview & Tech, Family Roots, Romantic Attachment, Leisure & Animals)
in the analytical SQLite database (chat.db).

Ensures that during Mode B (Comprehensive Personality Profiling), all investigative dimensions
and forensic sub-items are explicitly resolved (completed with evidence or marked as no_data after probing)
before assembling the final psychological dossier.
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

# Script location and path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_ROOT = os.path.dirname(PROJECT_DIR)
DEFAULT_DB_PATH = os.path.join(WORKSPACE_ROOT, "chat.db")

VALID_STATUSES = {"pending", "completed", "no_data", "not_applicable"}
RESOLVED_STATUSES = {"completed", "no_data", "not_applicable"}

# Complete forensic inventory across all 6 core life spheres
CHECKLIST_DEFINITIONS: List[Dict[str, str]] = [
    # -------------------------------------------------------------
    # Sphere A: Social Matrix & Friendship Dynamics
    # -------------------------------------------------------------
    {
        "item_id": "soc_authentic_vs_superficial",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Friendship Dynamics",
        "sub_item": "Authentic Friends vs. Superficial Contacts",
        "description": "Does the subject possess a genuine inner circle of close, trusted confidants, or are social contacts primarily superficial acquaintances, coworkers, or online gaming contacts?"
    },
    {
        "item_id": "soc_cadence_frequency",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Social Cadence & Interaction Modes",
        "sub_item": "Social Cadence & Meeting Frequency",
        "description": "How often do they actually meet friends offline in real life? Are offline hangouts routine, sporadic, or actively avoided in favor of digital-only exchanges?"
    },
    {
        "item_id": "soc_shared_activities",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Social Cadence & Interaction Modes",
        "sub_item": "Shared Social Activities",
        "description": "How do they spend shared time? (House gatherings, dining/pubs, shared gaming, sports, artistic/intellectual discussions, or mutual venting)."
    },
    {
        "item_id": "soc_altruism_helping",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Prosocial Stance & Altruism",
        "sub_item": "Altruism & Helping Others (Prosocial Stance)",
        "description": "Do they genuinely enjoy helping others, offering spontaneous assistance, time, advice, or practical aid? Is their helpfulness selfless and empathic, or transactional (expecting payback), driven by a savior/caretaker complex, or avoided altogether?"
    },
    {
        "item_id": "soc_paradigm_boundaries",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Friendship Boundaries & Relational Posture",
        "sub_item": "Friendship Paradigm & Boundaries",
        "description": "Do they view friends as authentic confidants, an admiring audience, or utilitarian assets? Do they maintain an exclusive inner circle while keeping others at arm's length?"
    },
    {
        "item_id": "soc_loyalty_doorslamming",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Relational Ruptures & Repair",
        "sub_item": "Loyalty vs. Door-Slamming",
        "description": "Do they repair relational fractures, or do they permanently sever ties (door-slam) upon the first perceived disloyalty or slight?"
    },
    {
        "item_id": "soc_envy_compersion_confidentiality",
        "sphere_id": "A",
        "sphere_name": "Social Matrix & Friendship Dynamics",
        "category": "Peer Comparisons & Discretion",
        "sub_item": "Envy vs. Compersion & Confidentiality",
        "description": "How do they react to peers' achievements? Genuine pride vs. passive-aggressive minimization, envy, or anxious comparison. Do they guard secrets faithfully or instrumentalize gossip?"
    },

    # -------------------------------------------------------------
    # Sphere B: Professional Sphere, Work Ethic, Ambitions & Financial Psychology
    # -------------------------------------------------------------
    {
        "item_id": "prof_work_ethic",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Work Ethic & Diligence",
        "sub_item": "Work Ethic & Diligence (Hard Worker vs. Slacker)",
        "description": "Are they a conscientious grinder/workaholic ('pracuś'), driven by perfectionism and duty, or do they slack off ('obijanie się'), procrastinate, coast, or do the bare minimum?"
    },
    {
        "item_id": "prof_ambitions_declared",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Aspirations, Ambitions & Plan Execution Track Record",
        "sub_item": "Declared Ambitions",
        "description": "What scale of ambition do they articulate (career pivots, startups, creative works, degrees, relocations)?"
    },
    {
        "item_id": "prof_ambitions_followthrough",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Aspirations, Ambitions & Plan Execution Track Record",
        "sub_item": "Follow-Through vs. Phantom Declarations",
        "description": "Over the longitudinal timeline, do they systematically execute declared plans, hit milestones, and follow through, OR do ambitious declarations evaporate into empty words, perpetual postponement, and wishful thinking?"
    },
    {
        "item_id": "prof_ambitions_unfulfilled",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Aspirations, Ambitions & Plan Execution Track Record",
        "sub_item": "Specific Unfulfilled Ambitions & Abandoned Goals (The Catalogue of Unrealized Dreams)",
        "description": "Explicitly identify, itemize, and name concrete unfulfilled ambitions, abandoned ventures, uncompleted qualifications/degrees, dropped projects, or deferred life paths (exact envisioned ambition, date declared, stall stage, true blocker, psychic wound vs mature mourning)."
    },
    {
        "item_id": "prof_coping_failure",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Aspirations, Ambitions & Plan Execution Track Record",
        "sub_item": "Coping with Failure & Rationalization",
        "description": "How do they handle stalled projects or unrealized dreams? Mature self-reflection and realistic recalibration vs. externalized blame (blaming systems, bosses, bad timing) and rationalization."
    },
    {
        "item_id": "prof_team_vs_lone_wolf",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Professional Collaboration",
        "sub_item": "Team Player vs. Lone Wolf",
        "description": "Are they cooperative and supportive in group endeavors, or individualistic, territorial, or resistant to shared ownership and teamwork?"
    },
    {
        "item_id": "prof_authority_relations",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Professional Collaboration",
        "sub_item": "Authority Relations & Hierarchy Stance",
        "description": "Respect for meritocratic leadership vs. knee-jerk defiance, submissiveness, cynical contempt for hierarchy, or impostor syndrome."
    },
    {
        "item_id": "prof_money_attitude",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Financial Psychology & Spending Habits",
        "sub_item": "Attitude Toward Money",
        "description": "Is money viewed as existential safety, scorecard of self-worth, an instrument of autonomy, or an object of chronic anxiety?"
    },
    {
        "item_id": "prof_frugality_vs_lavishness",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Financial Psychology & Spending Habits",
        "sub_item": "Frugality vs. Lavishness / Extravagance (Oszczędność vs. Rozrzutność)",
        "description": "Calculated, restrictive saver vs. impulsive, lavish spender. Do they indulge in higher-end lifestyle spending or show extreme frugality, guilt, or anxiety when spending money?"
    },
    {
        "item_id": "prof_premium_vs_budget",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Financial Psychology & Spending Habits",
        "sub_item": "Appetite for Premium vs. Budget Goods",
        "description": "Preference for expensive, flagship consumer electronics and branded items (smartphones, premium gadgets, designer goods) vs. deliberate satisfaction with economical, functional, cheaper alternatives."
    },
    {
        "item_id": "prof_budgeting_dynamics",
        "sphere_id": "B",
        "sphere_name": "Professional Sphere, Work Ethic, Ambitions & Financial Psychology",
        "category": "Financial Psychology & Spending Habits",
        "sub_item": "Everyday Budgeting & Financial Dynamics",
        "description": "How do they handle everyday budgeting, luxury purchases, debts, investments, or treating others?"
    },

    # -------------------------------------------------------------
    # Sphere C: Worldview, Politics & Technology Stance
    # -------------------------------------------------------------
    {
        "item_id": "world_political_orientation",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Doctrinal & Partisan Orientation",
        "description": "Explicit political stance (conservative, liberal, libertarian, left-wing, centrist, or apolitical/disillusioned), stance on governance, civic duties, and societal order."
    },
    {
        "item_id": "world_political_figures",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Sympathies Toward Political Figures & Movements",
        "description": "Stance toward specific political leaders, candidates, or political movements discussed in the archive (admiration, revulsion, or reflective neutrality)."
    },
    {
        "item_id": "world_civic_motivations",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Civic & Electoral Motivations",
        "description": "What drives their voting decisions or civic behavior? (Programmatic ideology vs. affective/emotional impulses, e.g. voting out of sympathy or pity vs. civic duty vs. cynical disengagement)."
    },
    {
        "item_id": "world_nations_nationalities",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Stance Toward Nations & Nationalities",
        "description": "Attitudes toward specific countries, foreign cultures, and nationalities (curiosity, warmth, cosmopolitanism vs. prejudice, skepticism, or ethnocentric distance)."
    },
    {
        "item_id": "world_discrimination_racism",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Ethical Stance on Discrimination & Racism",
        "description": "Evaluation of prejudice, discrimination, xenophobia, or racism (does the subject express or tolerate ethnic stereotyping, or actively uphold egalitarianism, fairness, and cultural tolerance?)."
    },
    {
        "item_id": "world_geopolitical_alignments",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Geopolitical & Cultural Alignments",
        "description": "Positioning regarding international conflicts, cultural sovereignty, and religious/ethnic solidarity."
    },
    {
        "item_id": "world_political_tolerance",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Socio-Political Beliefs & Civic Orientation",
        "sub_item": "Boundary Maintenance in Political Debates",
        "description": "Tolerance when interlocutors express opposing political or ideological views (collaborative pluralism vs. rigid boundary setting, e.g. demanding mutual respect and non-imposition vs. relational rupture)."
    },
    {
        "item_id": "world_tech_ai_posture",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Attitude Toward AI & Modern Technology",
        "sub_item": "AI & Tech Posture",
        "description": "Are they enthusiastic early adopters, pragmatic utilitarians, philosophical skeptics, or indifferent/uninterested in modern tech trends?"
    },
    {
        "item_id": "world_tech_reaction_innovations",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Attitude Toward AI & Modern Technology",
        "sub_item": "Reaction to Introduced Tools & Innovations",
        "description": "When an interlocutor recommends or introduces a new digital tool, software, or technology, does the subject show curiosity and try it, or do they simply show a lack of interest, shrug it off, or prefer familiar routines?"
    },
    {
        "item_id": "world_tech_practical_usage",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Attitude Toward AI & Modern Technology",
        "sub_item": "Practical Digital Tool Usage",
        "description": "How do they actually utilize digital infrastructure? (Advanced workflows and intellectual exploration vs. purely basic communication, administrative utilities, and low-friction mobile games)."
    },
    {
        "item_id": "world_cognitive_debate_style",
        "sphere_id": "C",
        "sphere_name": "Worldview, Politics & Technology Stance",
        "category": "Cognitive Style & Epistemology",
        "sub_item": "Cognitive Style in Debate",
        "description": "Do they lean on empirical evidence and formal logic, or emotional appeal and moral superiority? Do they respect ideological opponents or dehumanize them?"
    },

    # -------------------------------------------------------------
    # Sphere D: Family Roots, Parental Imprints & Domestic Environment
    # -------------------------------------------------------------
    {
        "item_id": "fam_parental_imprints",
        "sphere_id": "D",
        "sphere_name": "Family Roots, Parental Imprints & Domestic Environment",
        "category": "Family Roots & Parental Imprints",
        "sub_item": "Parental Imprints",
        "description": "Mother and father archetypes; presence of conditional love, harsh discipline, emotional neglect, or overprotection."
    },
    {
        "item_id": "fam_sibling_parentification",
        "sphere_id": "D",
        "sphere_name": "Family Roots, Parental Imprints & Domestic Environment",
        "category": "Family Roots & Parental Imprints",
        "sub_item": "Sibling Dynamics & Parentification",
        "description": "Were they forced to take on adult caretaker roles prematurely? Sibling relationships and burdens."
    },
    {
        "item_id": "fam_generational_traps",
        "sphere_id": "D",
        "sphere_name": "Family Roots, Parental Imprints & Domestic Environment",
        "category": "Family Roots & Parental Imprints",
        "sub_item": "Generational Traps",
        "description": "Did they witness an entrapped or unhappy parental marriage? How does this dictate their fear of commitment?"
    },
    {
        "item_id": "fam_domestic_order_chaos",
        "sphere_id": "D",
        "sphere_name": "Family Roots, Parental Imprints & Domestic Environment",
        "category": "Approach to Domestic Order & Living Space",
        "sub_item": "Orderliness vs. Chaos",
        "description": "Meticulous cleanliness and structured minimalism vs. high clutter tolerance, disorganization, or chronic mess."
    },
    {
        "item_id": "fam_domestic_mirror",
        "sphere_id": "D",
        "sphere_name": "Family Roots, Parental Imprints & Domestic Environment",
        "category": "Approach to Domestic Order & Living Space",
        "sub_item": "Domestic Environment as Psychological Mirror",
        "description": "How does their living space reflect their internal state? (E.g. compulsive cleaning as a stress-relief mechanism vs. neglecting environment during depressive/overwhelmed episodes)."
    },

    # -------------------------------------------------------------
    # Sphere E: Romantic Attachment & Relational Patterns
    # -------------------------------------------------------------
    {
        "item_id": "rom_relational_history",
        "sphere_id": "E",
        "sphere_name": "Romantic Attachment & Relational Patterns",
        "category": "Romantic History & Archetypes",
        "sub_item": "Relational History & Archetypes",
        "description": "Tracing romantic partners, breakups, betrayals, and formative lessons across the timeline."
    },
    {
        "item_id": "rom_intimacy_ceilings",
        "sphere_id": "E",
        "sphere_name": "Romantic Attachment & Relational Patterns",
        "category": "Intimacy Dynamics",
        "sub_item": "Intimacy Ceilings & Push-Pull Dynamics",
        "description": "At what point does closeness trigger defensive anxiety or deactivating maneuvers?"
    },
    {
        "item_id": "rom_conflict_resolution",
        "sphere_id": "E",
        "sphere_name": "Romantic Attachment & Relational Patterns",
        "category": "Intimacy Dynamics",
        "sub_item": "Conflict Resolution in Romance",
        "description": "Reconnection and repair attempts vs. emotional stonewalling, scorekeeping, or dramatic exits."
    },

    # -------------------------------------------------------------
    # Sphere F: Leisure, Sports, Travel, Vacations & Relationship with Animals
    # -------------------------------------------------------------
    {
        "item_id": "leis_free_time_hobbies",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Free Time & Hobbies",
        "sub_item": "Free Time & Hobbies (Restoration Modes)",
        "description": "How do they actively choose to spend discretionary time? Passive consumption (scrolling, streaming) vs. active passions (gaming, reading, creative arts, physical sports, technical tinkering, solo contemplation)."
    },
    {
        "item_id": "leis_sports_exercise_habits",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Sports & Physical Activity",
        "sub_item": "Exercise Habits & Preferences",
        "description": "Do they practice sports or physical training (gym, running, swimming, cycling, team sports, martial arts, fitness classes)? Do they follow/watch sports as a spectator?"
    },
    {
        "item_id": "leis_sports_function_culture",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Sports & Physical Activity",
        "sub_item": "Function of Physical Culture",
        "description": "Is exercise a discipline, a stress-relief mechanism, an aesthetic body-image drive, or do they express active aversion/apathy toward physical exertion (sedentary lifestyle)?"
    },
    {
        "item_id": "leis_vacation_style_structure",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Vacation & Holiday Style",
        "sub_item": "Style & Structure",
        "description": "How do they spend vacations and time off? Rigidly planned itineraries vs. spontaneous drifting; resort comfort vs. adventurous exploration; traveling solo vs. with partners/friends."
    },
    {
        "item_id": "leis_vacation_decompression",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Vacation & Holiday Style",
        "sub_item": "Psychological Decompression",
        "description": "Can they genuinely unplug from work and duties, or do they carry anxiety and hyper-vigilance into their time off?"
    },
    {
        "item_id": "leis_travel_drivers",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Travel Motivations & Modus Operandi",
        "sub_item": "Travel Drivers & Motivations",
        "description": "Driven by cultural curiosity, escape from routine, wanderlust, romantic getaways, or staying grounded as a committed homebody."
    },
    {
        "item_id": "leis_travel_pattern",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Travel Motivations & Modus Operandi",
        "sub_item": "Travel Pattern",
        "description": "Domestic getaways vs. international travel, high-frequency nomadism vs. rare, carefully curated journeys."
    },
    {
        "item_id": "leis_animals_pet_ownership",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Relationship with Animals & Pets",
        "sub_item": "Pet Ownership & Affection",
        "description": "Do they have pets (dogs, cats, etc.), desire pets, or avoid them?"
    },
    {
        "item_id": "leis_animals_empathy_bond",
        "sphere_id": "F",
        "sphere_name": "Leisure, Sports, Travel, Vacations & Relationship with Animals",
        "category": "Relationship with Animals & Pets",
        "sub_item": "Emotional Bond & Empathy",
        "description": "How do they interact with and talk about animals? Animal empathy serves as a potent window into their instinctual warmth, capacity for unconditional care, or sensory/cleanliness boundaries."
    }
]


def ensure_checklist_table(conn: sqlite3.Connection):
    """Create the life_spheres_checklist and metadata tables and indexes if they do not exist."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS life_spheres_checklist (
        chat_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        sphere_id TEXT NOT NULL,
        sphere_name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_item TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        evidence_summary TEXT,
        query_terms_used TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, item_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_status ON life_spheres_checklist(chat_id, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_sphere ON life_spheres_checklist(chat_id, sphere_id);")
    conn.commit()


def is_checklist_waived(conn: sqlite3.Connection, chat_id: str) -> Tuple[bool, Optional[str]]:
    """Check if the checklist is currently flagged as waived/exempt in metadata."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"checklist_mode_{chat_id}",))
        row = cur.fetchone()
        if row and row[0] == "waived":
            cur.execute("SELECT value FROM metadata WHERE key = ?;", (f"checklist_waiver_reason_{chat_id}",))
            r_row = cur.fetchone()
            reason = r_row[0] if r_row else "Ad-hoc task / partial inquiry (full profiling not required)"
            return True, reason
    except Exception:
        pass
    return False, None


def waive_checklist(conn: sqlite3.Connection, chat_id: str, reason: str = "Ad-hoc task / partial inquiry") -> int:
    """
    Waive/disable the checklist for a chat by setting all pending items to 'not_applicable'
    and recording the exemption status in the metadata table.
    Returns the count of waived items.
    """
    ensure_checklist_table(conn)
    cur = conn.cursor()
    now_iso = datetime.now().isoformat()

    # Record in metadata table
    cur.execute("""
    INSERT INTO metadata (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
    """, (f"checklist_mode_{chat_id}", "waived"))
    cur.execute("""
    INSERT INTO metadata (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
    """, (f"checklist_waiver_reason_{chat_id}", reason))

    # Update all pending items in life_spheres_checklist to 'not_applicable'
    notes = f"Exempt/Waived: {reason}"
    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = 'not_applicable', evidence_summary = ?, updated_at = ?
    WHERE chat_id = ? AND status = 'pending';
    """, (notes, now_iso, chat_id))
    waived_count = cur.rowcount
    conn.commit()
    return waived_count


def enable_checklist(conn: sqlite3.Connection, chat_id: str) -> int:
    """
    Re-enable the checklist for full profiling: removes waiver from metadata
    and resets not_applicable items back to pending.
    Returns the count of re-enabled items.
    """
    ensure_checklist_table(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM metadata WHERE key IN (?, ?);", (f"checklist_mode_{chat_id}", f"checklist_waiver_reason_{chat_id}"))
    now_iso = datetime.now().isoformat()
    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = 'pending', evidence_summary = '', updated_at = ?
    WHERE chat_id = ? AND status = 'not_applicable';
    """, (now_iso, chat_id))
    re_enabled = cur.rowcount
    conn.commit()
    return re_enabled


def resolve_chat_id(conn: sqlite3.Connection, chat_arg: Optional[str]) -> str:
    """Resolve explicit chat_id or automatically determine if only one chat exists."""
    cur = conn.cursor()
    if chat_arg:
        # Match chat_id or chat_name
        cur.execute("SELECT chat_id FROM chats WHERE chat_id = ? OR chat_name = ?;", (chat_arg, chat_arg))
        row = cur.fetchone()
        if row:
            return row[0]
        # Return sanitized or explicit argument even if not cataloged yet
        return chat_arg

    cur.execute("SELECT chat_id, chat_name FROM chats;")
    rows = cur.fetchall()
    if not rows:
        raise ValueError("No chats found in database. Ingest chat logs first via db_builder.py.")
    if len(rows) == 1:
        return rows[0][0]

    # Multiple chats found
    names = ", ".join(f"{r[0]} ('{r[1]}')" for r in rows)
    raise ValueError(
        f"Multiple chats found in database ({names}).\n"
        f"Please specify --chat <chat_id> to audit a specific chat, "
        f"or --chat global (or --chat <subject_name>) for a cross-chat personality profile."
    )


def init_checklist(conn: sqlite3.Connection, chat_id: str, reset: bool = False) -> Tuple[int, int]:
    """
    Initialize checklist items for a chat.
    If reset is True, clears existing items for this chat.
    Otherwise, inserts missing items while preserving already updated statuses.
    Returns (inserted_count, total_count).
    """
    ensure_checklist_table(conn)
    cur = conn.cursor()

    if reset:
        cur.execute("DELETE FROM life_spheres_checklist WHERE chat_id = ?;", (chat_id,))
        conn.commit()

    # Find which item_ids already exist for this chat
    cur.execute("SELECT item_id FROM life_spheres_checklist WHERE chat_id = ?;", (chat_id,))
    existing_ids = {r[0] for r in cur.fetchall()}

    now_iso = datetime.now().isoformat()
    inserted = 0

    for item in CHECKLIST_DEFINITIONS:
        if item["item_id"] not in existing_ids:
            cur.execute("""
            INSERT INTO life_spheres_checklist (
                chat_id, item_id, sphere_id, sphere_name, category, sub_item,
                description, status, evidence_summary, query_terms_used, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', '', ?);
            """, (
                chat_id,
                item["item_id"],
                item["sphere_id"],
                item["sphere_name"],
                item["category"],
                item["sub_item"],
                item["description"],
                now_iso
            ))
            inserted += 1

    conn.commit()
    return inserted, len(CHECKLIST_DEFINITIONS)


def get_checklist_stats(conn: sqlite3.Connection, chat_id: str) -> Dict[str, Any]:
    """Compute completion statistics grouped by status and by sphere, including waiver status."""
    ensure_checklist_table(conn)
    cur = conn.cursor()

    is_waived, waiver_reason = is_checklist_waived(conn, chat_id)

    cur.execute("""
    SELECT status, count(*)
    FROM life_spheres_checklist
    WHERE chat_id = ?
    GROUP BY status;
    """, (chat_id,))
    status_counts = {r[0]: r[1] for r in cur.fetchall()}

    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    no_data = status_counts.get("no_data", 0)
    not_applicable = status_counts.get("not_applicable", 0)
    pending = status_counts.get("pending", 0)
    resolved = completed + no_data + not_applicable

    pct = (resolved / total * 100.0) if total > 0 else 0.0

    # Stats per sphere
    cur.execute("""
    SELECT sphere_id, sphere_name, status, count(*)
    FROM life_spheres_checklist
    WHERE chat_id = ?
    GROUP BY sphere_id, sphere_name, status
    ORDER BY sphere_id;
    """, (chat_id,))
    sphere_rows = cur.fetchall()

    spheres: Dict[str, Dict[str, Any]] = {}
    for sid, sname, st, cnt in sphere_rows:
        if sid not in spheres:
            spheres[sid] = {
                "sphere_id": sid,
                "sphere_name": sname,
                "total": 0,
                "completed": 0,
                "no_data": 0,
                "not_applicable": 0,
                "pending": 0
            }
        spheres[sid]["total"] += cnt
        spheres[sid][st] = cnt

    for sid in spheres:
        s = spheres[sid]
        s_resolved = s["completed"] + s["no_data"] + s["not_applicable"]
        s["percent"] = (s_resolved / s["total"] * 100.0) if s["total"] > 0 else 0.0

    return {
        "chat_id": chat_id,
        "is_waived": is_waived,
        "waiver_reason": waiver_reason,
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "completed": completed,
        "no_data": no_data,
        "not_applicable": not_applicable,
        "percent": pct,
        "is_complete": (pending == 0 and total > 0),
        "spheres": list(spheres.values())
    }


def update_checklist_item(
    conn: sqlite3.Connection,
    chat_id: str,
    item_id: str,
    status: str,
    notes: Optional[str] = None,
    queries: Optional[str] = None
) -> bool:
    """Update status, notes, and query terms for a specific checklist item."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid options: {', '.join(sorted(VALID_STATUSES))}")

    ensure_checklist_table(conn)
    cur = conn.cursor()

    cur.execute("SELECT item_id, evidence_summary, query_terms_used FROM life_spheres_checklist WHERE chat_id = ? AND item_id = ?;", (chat_id, item_id))
    row = cur.fetchone()
    if not row:
        return False

    old_notes = row[1] or ""
    old_queries = row[2] or ""

    new_notes = notes if notes is not None else old_notes
    new_queries = queries if queries is not None else old_queries
    now_iso = datetime.now().isoformat()

    cur.execute("""
    UPDATE life_spheres_checklist
    SET status = ?, evidence_summary = ?, query_terms_used = ?, updated_at = ?
    WHERE chat_id = ? AND item_id = ?;
    """, (status, new_notes, new_queries, now_iso, chat_id, item_id))
    conn.commit()
    return True


def list_checklist_items(
    conn: sqlite3.Connection,
    chat_id: str,
    status_filter: Optional[str] = None,
    sphere_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List checklist items matching optional status and sphere filters."""
    ensure_checklist_table(conn)
    cur = conn.cursor()

    sql = """
    SELECT item_id, sphere_id, sphere_name, category, sub_item, description,
           status, evidence_summary, query_terms_used, updated_at
    FROM life_spheres_checklist
    WHERE chat_id = ?
    """
    params: List[Any] = [chat_id]

    if status_filter:
        if status_filter == "resolved":
            sql += " AND status IN ('completed', 'no_data', 'not_applicable')"
        elif status_filter == "unresolved":
            sql += " AND status = 'pending'"
        elif status_filter in VALID_STATUSES:
            sql += " AND status = ?"
            params.append(status_filter)
        else:
            raise ValueError(f"Unknown status filter '{status_filter}'. Use: pending, completed, no_data, not_applicable, resolved, unresolved")

    if sphere_filter:
        clean_sf = sphere_filter.strip()
        if len(clean_sf) == 1:
            sql += " AND sphere_id = ?"
            params.append(clean_sf.upper())
        else:
            sql += " AND (sphere_id = ? OR sphere_name LIKE ?)"
            params.extend([clean_sf.upper(), f"%{clean_sf}%"])

    sql += " ORDER BY sphere_id, item_id;"
    cur.execute(sql, params)
    rows = cur.fetchall()

    return [
        {
            "item_id": r[0],
            "sphere_id": r[1],
            "sphere_name": r[2],
            "category": r[3],
            "sub_item": r[4],
            "description": r[5],
            "status": r[6],
            "evidence_summary": r[7] or "",
            "query_terms_used": r[8] or "",
            "updated_at": r[9]
        }
        for r in rows
    ]


def print_status_summary(stats: Dict[str, Any]):
    """Print a clean human-readable dashboard of checklist progress."""
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
    print(f"Progress: [{bar}] {stats['percent']:.1f}% ({stats['resolved']}/{stats['total']} resolved)")
    print(f"  ✓ Completed (Evidence Found):   {stats['completed']}")
    print(f"  ∅ No Data (Probed & Absent):    {stats['no_data']}")
    print(f"  ⊘ Not Applicable / Waived:      {stats['not_applicable']}")
    print(f"  ⏳ Pending Audit:                {stats['pending']}")
    print("-" * 72)
    print("Spheres Breakdown:")
    for s in stats["spheres"]:
        s_bar_len = 16
        s_filled = int(round(s_bar_len * s["percent"] / 100.0))
        s_bar = "█" * s_filled + "░" * (s_bar_len - s_filled)
        print(f"  [{s['sphere_id']}] {s['sphere_name'][:36]:<36} [{s_bar}] {s['percent']:>5.1f}%  (Pending: {s['pending']})")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(
        description="Life Spheres Forensic Checklist & Verification Manager."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite analytical database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--chat", "-C",
        type=str,
        default=None,
        help="Chat ID or chat name (auto-detected if only 1 chat exists in database)"
    )

    action_group = parser.add_mutually_exclusive_group(required=False)
    action_group.add_argument(
        "--init",
        action="store_true",
        help="Initialize checklist items in the database for the selected chat"
    )
    action_group.add_argument(
        "--status", "--summary",
        action="store_true",
        help="Display completion progress and breakdown across all 6 life spheres"
    )
    action_group.add_argument(
        "--list",
        action="store_true",
        help="List checklist items with their current statuses"
    )
    action_group.add_argument(
        "--update",
        type=str,
        metavar="ITEM_ID",
        help="Update status and notes for a specific checklist item_id"
    )
    action_group.add_argument(
        "--batch-update",
        nargs="+",
        metavar="ITEM_ID",
        help="Update multiple item_ids to the same status in one command"
    )
    action_group.add_argument(
        "--check",
        action="store_true",
        help="Pipeline Gate Verification: exits with 0 if all items are resolved or waived; exits with 1 if any pending items remain"
    )
    action_group.add_argument(
        "--waive", "--bypass", "--disable",
        action="store_true",
        help="Waive/disable the checklist for ad-hoc queries or tasks not requiring full life spheres profiling"
    )
    action_group.add_argument(
        "--enable",
        action="store_true",
        help="Re-enable the checklist for full profiling (clears waiver and resets waived items to pending)"
    )

    # Modification & Filtering arguments
    parser.add_argument(
        "--reason",
        type=str,
        default="Ad-hoc task / partial inquiry (full profiling not required)",
        help="Reason for waiving the checklist with --waive"
    )
    parser.add_argument(
        "--set-status",
        type=str,
        choices=list(VALID_STATUSES),
        help="Status to set for --update or --batch-update (pending, completed, no_data, not_applicable)"
    )
    parser.add_argument(
        "--notes", "--evidence",
        type=str,
        help="Evidence findings summary or probe attempt details for --update / --batch-update"
    )
    parser.add_argument(
        "--queries",
        type=str,
        help="Search query terms used during probing for --update / --batch-update"
    )
    parser.add_argument(
        "--filter-status",
        type=str,
        help="Filter items by status for --list (pending, completed, no_data, not_applicable, resolved, unresolved)"
    )
    parser.add_argument(
        "--sphere",
        type=str,
        help="Filter items by sphere ID (A, B, C, D, E, F) or name for --list"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Display detailed descriptions, notes, and query terms when using --list"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Force reinitialization of all checklist items to pending when using --init"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[!] Database file not found: {args.db}", file=sys.stderr)
        sys.exit(2)

    conn = sqlite3.connect(args.db)
    try:
        chat_id = resolve_chat_id(conn, args.chat)
    except Exception as e:
        print(f"[!] Error resolving chat: {e}", file=sys.stderr)
        sys.exit(2)

    # Default action if none specified: show status
    if not any([args.init, args.status, args.list, args.update, args.batch_update, args.check, args.waive, args.enable]):
        args.status = True

    # 1. Action: --waive / --disable
    if args.waive:
        waived_count = waive_checklist(conn, chat_id, reason=args.reason)
        if args.json:
            print(json.dumps({"action": "waive", "chat_id": chat_id, "waived_items": waived_count, "reason": args.reason}))
        else:
            print(f"[✓] Life spheres checklist WAIVED/DISABLED for chat '{chat_id}'.")
            print(f"    Reason: {args.reason}")
            print(f"    {waived_count} pending items marked as not_applicable. Full checklist audit is not required.")
        sys.exit(0)

    # 2. Action: --enable
    if args.enable:
        re_enabled = enable_checklist(conn, chat_id)
        if args.json:
            print(json.dumps({"action": "enable", "chat_id": chat_id, "re_enabled_items": re_enabled}))
        else:
            print(f"[✓] Life spheres checklist RE-ENABLED for chat '{chat_id}'.")
            print(f"    {re_enabled} items reset to pending. Full profiling audit active.")
        sys.exit(0)

    # 3. Action: --init
    if args.init:
        # Also clear any waiver on explicit init
        cur = conn.cursor()
        cur.execute("DELETE FROM metadata WHERE key IN (?, ?);", (f"checklist_mode_{chat_id}", f"checklist_waiver_reason_{chat_id}"))
        conn.commit()
        inserted, total = init_checklist(conn, chat_id, reset=args.reset)
        if args.json:
            print(json.dumps({"action": "init", "chat_id": chat_id, "inserted": inserted, "total_items": total}))
        else:
            print(f"[✓] Checklist initialized for chat '{chat_id}'. {inserted} new items created (Total: {total}).")
        sys.exit(0)

    # 2. Action: --update
    if args.update:
        if not args.set_status:
            print("[!] Error: --set-status <completed|no_data|not_applicable|pending> is required with --update.", file=sys.stderr)
            sys.exit(1)
        ok = update_checklist_item(conn, chat_id, args.update, args.set_status, args.notes, args.queries)
        if not ok:
            print(f"[!] Item ID '{args.update}' not found for chat '{chat_id}'. Run --init first if uninitialized.", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"action": "update", "chat_id": chat_id, "item_id": args.update, "status": args.set_status}))
        else:
            print(f"[✓] Updated '{args.update}' -> status: {args.set_status}")
        sys.exit(0)

    # 3. Action: --batch-update
    if args.batch_update:
        if not args.set_status:
            print("[!] Error: --set-status is required with --batch-update.", file=sys.stderr)
            sys.exit(1)
        updated_count = 0
        missing = []
        for item_id in args.batch_update:
            if update_checklist_item(conn, chat_id, item_id, args.set_status, args.notes, args.queries):
                updated_count += 1
            else:
                missing.append(item_id)
        if args.json:
            print(json.dumps({"action": "batch_update", "chat_id": chat_id, "updated": updated_count, "missing": missing}))
        else:
            print(f"[✓] Batch updated {updated_count} items to '{args.set_status}'.")
            if missing:
                print(f"[!] Warning: {len(missing)} items not found: {', '.join(missing)}")
        sys.exit(0)

    # 4. Action: --list
    if args.list:
        items = list_checklist_items(conn, chat_id, status_filter=args.filter_status, sphere_filter=args.sphere)
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            if not items:
                print(f"[*] No checklist items found matching criteria for chat '{chat_id}'.")
            else:
                print(f"[*] Showing {len(items)} items for chat '{chat_id}':\n")
                status_icons = {
                    "completed": "✓ [COMPLETED]",
                    "no_data": "∅ [NO_DATA]",
                    "not_applicable": "⊘ [NOT_APPLICABLE]",
                    "pending": "⏳ [PENDING]"
                }
                for it in items:
                    icon = status_icons.get(it["status"], it["status"])
                    print(f"• [{it['sphere_id']}] {it['item_id']} | {icon}")
                    print(f"  Category: {it['category']} -> {it['sub_item']}")
                    if args.detailed:
                        print(f"  Probing Question: {it['description']}")
                        if it['evidence_summary']:
                            print(f"  Notes / Evidence: {it['evidence_summary']}")
                        if it['query_terms_used']:
                            print(f"  Queries Executed: {it['query_terms_used']}")
                    print()
        sys.exit(0)

    # 5. Action: --check (Pipeline Blocking Gate)
    if args.check:
        stats = get_checklist_stats(conn, chat_id)
        if stats.get("is_waived"):
            if args.json:
                print(json.dumps({"gate": "PASSED_EXEMPT", "stats": stats}))
            else:
                print(f"[✓] PIPELINE GATE PASSED (EXEMPT): Life spheres checklist is WAIVED/DISABLED for chat '{chat_id}'.")
                print(f"    Reason: {stats.get('waiver_reason')}")
                print(f"    No subpoints are required for this ad-hoc/partial task.")
            sys.exit(0)

        if stats["total"] == 0:
            print(f"[!] Blocking Gate FAILED: Checklist is not initialized for chat '{chat_id}'. Run --init first.", file=sys.stderr)
            sys.exit(1)

        if stats["is_complete"]:
            if args.json:
                print(json.dumps({"gate": "PASSED", "stats": stats}))
            else:
                print(f"[✓] PIPELINE GATE PASSED: All {stats['total']} life spheres dimensions resolved for chat '{chat_id}'.")
                print(f"    Completed: {stats['completed']} | No Data: {stats['no_data']} | Not Applicable / Waived: {stats['not_applicable']} | Pending: 0")
            sys.exit(0)
        else:
            pending_items = list_checklist_items(conn, chat_id, status_filter="pending")
            if args.json:
                print(json.dumps({"gate": "FAILED", "stats": stats, "pending_items": pending_items}))
            else:
                print(f"[!] PIPELINE GATE BLOCKED: {stats['pending']} / {stats['total']} items still pending investigation for chat '{chat_id}'!", file=sys.stderr)
                print(f"    You must audit every item and mark either 'completed' (evidence found) or 'no_data' (attempted & absent) before report assembly.\n", file=sys.stderr)
                print("Remaining pending items:", file=sys.stderr)
                for it in pending_items:
                    print(f"  - [{it['sphere_id']}] {it['item_id']}: {it['sub_item']} ({it['category']})", file=sys.stderr)
            sys.exit(1)

    # 6. Action: --status (default)
    if args.status:
        stats = get_checklist_stats(conn, chat_id)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print_status_summary(stats)
        sys.exit(0)


if __name__ == "__main__":
    main()
