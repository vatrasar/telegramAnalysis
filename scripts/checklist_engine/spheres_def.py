"""Life Spheres checklist definitions and semantic requirements."""

from typing import List, Dict, Set

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

# Core abstract, attitudinal, and psychological items that CANNOT be validated by literal keyword matching alone.
MANDATORY_SEMANTIC_ITEMS: Set[str] = {
    # Sphere B: Work Ethic, Ambitions & Financial Psychology
    "prof_work_ethic",
    "prof_ambitions_declared",
    "prof_ambitions_followthrough",
    "prof_ambitions_unfulfilled",
    "prof_coping_failure",
    "prof_team_vs_lone_wolf",
    "prof_authority_relations",
    "prof_money_attitude",
    "prof_frugality_vs_lavishness",
    "prof_premium_vs_budget",
    "prof_budgeting_dynamics",
    # Sphere C: Worldview, Politics & Technology Stance
    "world_political_orientation",
    "world_political_figures",
    "world_civic_motivations",
    "world_nations_nationalities",
    "world_discrimination_racism",
    "world_geopolitical_alignments",
    "world_political_tolerance",
    "world_tech_ai_posture",
    "world_tech_reaction_innovations",
    "world_tech_practical_usage",
    "world_cognitive_debate_style",
    # Sphere E: Romantic Attachment & Relational Patterns
    "rom_relational_history",
    "rom_intimacy_ceilings",
    "rom_conflict_resolution",
    # Sphere A: Social Matrix & Friendship Dynamics
    "soc_altruism_helping",
    "soc_paradigm_boundaries",
    "soc_loyalty_doorslamming",
    "soc_envy_compersion_confidentiality",
    # Sphere D: Family Roots & Parental Imprints
    "fam_parental_imprints",
    "fam_sibling_parentification",
    "fam_generational_traps",
    "fam_domestic_mirror"
}
