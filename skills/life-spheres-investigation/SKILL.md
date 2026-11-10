---
name: life-spheres-investigation
description: >-
  Investigative probing criteria, forensic diagnostic questions, database checklist toolchain (checklist.py),
  and bilingual search lexicon (Polish FTS5 keywords and English semantic queries) for auditing the 6 foundational
  life spheres (Social Matrix, Work & Ambitions, Worldview & Tech, Family Roots & Domestic Order, Romantic Attachment,
  Leisure & Animals). Use during Phase 4 life spheres audits, behavioral probing, managing the investigation checklist,
  or running targeted queries via query_chat.py.
---

# Life Spheres Investigation, Database Checklist & Behavioral Probing Skill

This skill defines the operational workflow, forensic probing criteria, database checklist management, bilingual search vocabulary, and query recipes used to investigate longitudinal chat logs across foundational life spheres and behavioral dimensions.

---

## 1. Overview

Longitudinal chat archives contain rich behavioral evidence, but critical lifestyle indicators (e.g. domestic order, work ethic, unfulfilled ambitions, financial psychology, altruism, relationship with animals) are dispersed across thousands of messages.

This skill equips the agent with:
1. **The 6 Core Life Spheres Probing Framework:** Concrete forensic questions and 46 standardized item IDs across all lifestyle domains.
2. **The Life Spheres Database Checklist Manager (`checklist.py`):** SQLite persistence layer in `chat.db` enforcing exhaustive auditing of every dimension (tracking evidence found vs. unmentioned/absent data).
3. **The Master Bilingual Search Lexicon:** Curated Polish lexical terms for SQLite FTS5 queries (`-s`, `-st`) and English semantic queries for vector search (`--semantic`).
4. **Query Toolchain Recipes:** Concrete CLI commands via `query_chat.py` to retrieve messages, inspect dialogue threads, and trace causal chains.
5. **Dual-Layer Evidentiary Protocol:** 100% database tracking rigor (logging `completed` or `no_data` for all items) combined with clean narrative report delivery (omitting unmentioned topics without hollow boilerplates).

---

## 2. When to Use

Activate this skill whenever:
- Auditing the **6 Core Life Spheres** during Phase 4 of an in-depth psychological investigation (Mode B).
- Initializing, updating, or verifying the investigation database checklist via `checklist.py`.
- Searching for specific behavioral indicators, unfulfilled ambitions, work ethic, domestic order, or spending patterns.
- Executing lexical (`-s` / `-st`) or semantic (`--semantic`) searches with `query_chat.py` on `chat.db`.
- Fact-checking or verifying specific lifestyle claims against the chat record.

---

## 3. The 6 Core Life Spheres (Forensic Probing Criteria & Item Inventory)

Use these detailed criteria and standardized `item_id`s when auditing the archive across foundational domains:

### A. Social Matrix & Friendship Dynamics
- `soc_authentic_vs_superficial` — **Authentic Friends vs. Superficial Contacts:** Does the subject possess a genuine inner circle of close, trusted confidants, or are social contacts primarily superficial acquaintances, coworkers, or online gaming contacts?
- `soc_cadence_frequency` — **Social Cadence & Meeting Frequency:** How often do they actually meet friends offline in real life? Are offline hangouts routine, sporadic, or actively avoided in favor of digital-only exchanges?
- `soc_shared_activities` — **Shared Social Activities:** How do they spend shared time? (House gatherings, dining/pubs, shared gaming, sports, artistic/intellectual discussions, or mutual venting).
- `soc_altruism_helping` — **Altruism & Helping Others (Prosocial Stance):** Do they genuinely enjoy helping others, offering spontaneous assistance, time, advice, or practical aid? Is their helpfulness selfless and empathic, or transactional (expecting payback), driven by a savior/caretaker complex, or avoided altogether?
- `soc_paradigm_boundaries` — **Friendship Paradigm & Boundaries:** Do they view friends as authentic confidants, an admiring audience, or utilitarian assets? Do they maintain an exclusive inner circle while keeping others at arm's length?
- `soc_loyalty_doorslamming` — **Loyalty vs. Door-Slamming:** Do they repair relational fractures, or do they permanently sever ties (*door-slam*) upon the first perceived disloyalty or slight?
- `soc_envy_compersion_confidentiality` — **Envy vs. Compersion & Confidentiality:** How do they react to peers' achievements? Genuine pride vs. passive-aggressive minimization, envy, or anxious comparison. Do they guard secrets faithfully or instrumentalize gossip?

---

### B. Professional Sphere, Work Ethic, Ambitions & Financial Psychology
- `prof_work_ethic` — **Work Ethic & Diligence (Hard Worker vs. Slacker):** Are they a conscientious grinder/workaholic ("pracuś"), driven by perfectionism and duty, or do they slack off ("obijanie się"), procrastinate, coast, or do the bare minimum?
- `prof_ambitions_declared` — **Aspirations & Ambitions: Declared Ambitions:** What scale of ambition do they articulate (career pivots, startups, creative works, degrees, relocations)?
- `prof_ambitions_followthrough` — **Aspirations & Ambitions: Follow-Through vs. Phantom Declarations:** Over the longitudinal timeline, do they systematically execute declared plans, hit milestones, and follow through, OR do ambitious declarations evaporate into empty words, perpetual postponement, and wishful thinking?
- `prof_ambitions_unfulfilled` — **Aspirations & Ambitions: Specific Unfulfilled Ambitions & Abandoned Goals (The Catalogue of Unrealized Dreams):**
  - Explicitly identify, itemize, and name the **concrete unfulfilled ambitions, abandoned ventures, uncompleted qualifications/degrees, dropped projects, or deferred life paths** revealed across the archive (e.g. *"wanted to launch a startup but never did"*, *"planned to study abroad"*, *"abandoned writing a book/creative work"*, *"dreamed of switching to medicine/IT but stayed in a safe job"*).
  - For each identified unfulfilled ambition, investigate:
    1. What was the exact envisioned ambition and when was it declared?
    2. At what stage did execution stall or derail?
    3. What was the true blocker (e.g. perfectionist paralysis, fear of public failure, lack of financial runway, loss of novelty, partner/parental discouragement)?
    4. Does it linger as an open psychic wound, a chronic source of melancholy/regret ("what could have been"), or was it maturely mourned and replaced?
- `prof_coping_failure` — **Aspirations & Ambitions: Coping with Failure & Rationalization:** How do they handle stalled projects or unrealized dreams? Mature self-reflection and realistic recalibration vs. externalized blame (blaming systems, bosses, bad timing) and rationalization.
- `prof_team_vs_lone_wolf` — **Team Player vs. Lone Wolf:** Are they cooperative and supportive in group endeavors, or individualistic, territorial, or resistant to shared ownership and teamwork?
- `prof_authority_relations` — **Authority Relations & Hierarchy Stance:** Respect for meritocratic leadership vs. knee-jerk defiance, submissiveness, cynical contempt for hierarchy, or impostor syndrome.
- `prof_money_attitude` — **Financial Psychology: Attitude Toward Money:** Is money viewed as existential safety, scorecard of self-worth, an instrument of autonomy, or an object of chronic anxiety?
- `prof_frugality_vs_lavishness` — **Financial Psychology: Frugality vs. Lavishness / Extravagance (Oszczędność vs. Rozrzutność):** Calculated, restrictive saver vs. impulsive, lavish spender. Do they indulge in higher-end lifestyle spending or show extreme frugality, guilt, or anxiety when spending money?
- `prof_premium_vs_budget` — **Financial Psychology: Appetite for Premium vs. Budget Goods:** Preference for expensive, flagship consumer electronics and branded items (e.g. desire for flagship smartphones, premium gadgets, designer goods) vs. deliberate satisfaction with economical, functional, cheaper alternatives.
- `prof_budgeting_dynamics` — **Financial Psychology: Everyday Budgeting & Financial Dynamics:** How do they handle everyday budgeting, luxury purchases, debts, investments, or treating others?

---

### C. Worldview, Politics & Technology Stance
- `world_political_orientation` — **Socio-Political Beliefs: Doctrinal & Partisan Orientation:** Explicit political stance (conservative, liberal, libertarian, left-wing, centrist, or apolitical/disillusioned), stance on governance, civic duties, and societal order.
- `world_political_figures` — **Socio-Political Beliefs: Sympathies Toward Political Figures & Movements:** Stance toward specific political leaders, candidates, or political movements discussed in the archive (admiration, revulsion, or reflective neutrality).
- `world_civic_motivations` — **Socio-Political Beliefs: Civic & Electoral Motivations:** What drives their voting decisions or civic behavior? (Programmatic ideology vs. affective/emotional impulses, e.g. voting out of sympathy or pity vs. civic duty vs. cynical disengagement).
- `world_nations_nationalities` — **Socio-Political Beliefs: Stance Toward Nations & Nationalities:** Attitudes toward specific countries, foreign cultures, and nationalities (curiosity, warmth, cosmopolitanism vs. prejudice, skepticism, or ethnocentric distance).
- `world_discrimination_racism` — **Socio-Political Beliefs: Ethical Stance on Discrimination & Racism:** Evaluation of prejudice, discrimination, xenophobia, or racism (does the subject express or tolerate ethnic stereotyping, or actively uphold egalitarianism, fairness, and cultural tolerance?).
- `world_geopolitical_alignments` — **Socio-Political Beliefs: Geopolitical & Cultural Alignments:** Positioning regarding international conflicts, cultural sovereignty, and religious/ethnic solidarity.
- `world_political_tolerance` — **Socio-Political Beliefs: Boundary Maintenance in Political Debates:** Tolerance when interlocutors express opposing political or ideological views (collaborative pluralism vs. rigid boundary setting, e.g. demanding mutual respect and non-imposition vs. relational rupture).
- `world_tech_ai_posture` — **Attitude Toward AI & Modern Technology: AI & Tech Posture:** Are they enthusiastic early adopters, pragmatic utilitarians, philosophical skeptics, or indifferent/uninterested in modern tech trends?
- `world_tech_reaction_innovations` — **Attitude Toward AI & Modern Technology: Reaction to Introduced Tools & Innovations:** When an interlocutor recommends or introduces a new digital tool, software, or technology, does the subject show curiosity and try it, or do they simply show a lack of interest, shrug it off, or prefer familiar routines? (Avoid forcing far-fetched psychological diagnoses when a reaction simply reflects standard disinterest).
- `world_tech_practical_usage` — **Attitude Toward AI & Modern Technology: Practical Digital Tool Usage:** How do they actually utilize digital infrastructure? (Advanced workflows and intellectual exploration vs. purely basic communication, administrative utilities, and low-friction mobile games).
- `world_cognitive_debate_style` — **Cognitive Style in Debate:** Do they lean on empirical evidence and formal logic, or emotional appeal and moral superiority? Do they respect ideological opponents or dehumanize them?

---

### D. Family Roots, Parental Imprints & Domestic Environment
- `fam_parental_imprints` — **Parental Imprints:** Mother and father archetypes; presence of conditional love, harsh discipline, emotional neglect, or overprotection.
- `fam_sibling_parentification` — **Sibling Dynamics & Parentification:** Were they forced to take on adult caretaker roles prematurely? Sibling relationships and burdens.
- `fam_generational_traps` — **Generational Traps:** Did they witness an entrapped or unhappy parental marriage? How does this dictate their fear of commitment?
- `fam_domestic_order_chaos` — **Approach to Domestic Order: Orderliness vs. Chaos:** Meticulous cleanliness and structured minimalism vs. high clutter tolerance, disorganization, or chronic mess.
- `fam_domestic_mirror` — **Approach to Domestic Order: Domestic Environment as Psychological Mirror:** How does their living space reflect their internal state? (E.g. compulsive cleaning as a stress-relief mechanism vs. neglecting environment during depressive/overwhelmed episodes).

---

### E. Romantic Attachment & Relational Patterns
- `rom_relational_history` — **Relational History & Archetypes:** Tracing romantic partners, breakups, betrayals, and formative lessons across the timeline.
- `rom_intimacy_ceilings` — **Intimacy Ceilings & Push-Pull Dynamics:** At what point does closeness trigger defensive anxiety or deactivating maneuvers?
- `rom_conflict_resolution` — **Conflict Resolution in Romance:** Reconnection and repair attempts vs. emotional stonewalling, scorekeeping, or dramatic exits.

---

### F. Leisure, Sports, Travel, Vacations & Relationship with Animals
- `leis_free_time_hobbies` — **Free Time & Hobbies (Restoration Modes):** How do they actively choose to spend discretionary time? Passive consumption (scrolling, streaming) vs. active passions (gaming, reading, creative arts, physical sports, technical tinkering, solo contemplation).
- `leis_sports_exercise_habits` — **Sports & Physical Activity: Exercise Habits & Preferences:** Do they practice sports or physical training (gym, running, swimming, cycling, team sports, martial arts, fitness classes)? Do they follow/watch sports as a spectator?
- `leis_sports_function_culture` — **Sports & Physical Activity: Function of Physical Culture:** Is exercise a discipline, a stress-relief mechanism, an aesthetic body-image drive, or do they express active aversion/apathy toward physical exertion (sedentary lifestyle)?
- `leis_vacation_style_structure` — **Vacation & Holiday Style: Style & Structure:** How do they spend vacations and time off? Rigidly planned itineraries vs. spontaneous drifting; resort comfort vs. adventurous exploration; traveling solo vs. with partners/friends.
- `leis_vacation_decompression` — **Vacation & Holiday Style: Psychological Decompression:** Can they genuinely unplug from work and duties, or do they carry anxiety and hyper-vigilance into their time off?
- `leis_travel_drivers` — **Travel: Motivations & Drivers:** Driven by cultural curiosity, escape from routine, wanderlust, romantic getaways, or staying grounded as a committed homebody.
- `leis_travel_pattern` — **Travel: Pattern:** Domestic getaways vs. international travel, high-frequency nomadism vs. rare, carefully curated journeys.
- `leis_animals_pet_ownership` — **Relationship with Animals: Pet Ownership & Affection:** Do they have pets (dogs, cats, etc.), desire pets, or avoid them?
- `leis_animals_empathy_bond` — **Relationship with Animals: Emotional Bond & Empathy:** How do they interact with and talk about animals? Animal empathy serves as a potent window into their instinctual warmth, capacity for unconditional care, or sensory/cleanliness boundaries.

---

## 4. The Database Checklist Manager (`checklist.py`)

During comprehensive profiling (Mode B), every dimension in the database must transition from `pending` to a resolved status (`completed`, `no_data`, or `not_applicable`).

### Valid Item Statuses:
- `pending`: Unexamined / audit in progress (initial state).
- `completed`: Audited, evidence found, analyzed and documented with citations.
- `no_data`: Audited via lexical and semantic queries, but unmentioned / absent in archive (the agent explicitly records probe attempts).
- `not_applicable`: Explicitly outside the scope of analysis.

### Command Toolchain:
```bash
# Initialize checklist in chat.db for the chat:
python3 project/scripts/checklist.py --init -C <chat_id>

# View overall progress and breakdown across spheres:
python3 project/scripts/checklist.py --status -C <chat_id>
# Or via query_chat:
python3 project/scripts/query_chat.py --checklist -C <chat_id>

# List items (with optional filters):
python3 project/scripts/checklist.py --list -C <chat_id> --filter-status pending
python3 project/scripts/checklist.py --list -C <chat_id> --sphere B --detailed

# Mark an item as COMPLETED (evidence found):
python3 project/scripts/checklist.py -C <chat_id> --update prof_ambitions_unfulfilled \
  --set-status completed \
  --notes "Identified uncompleted IT pivot [#1234 | 2021-03-04]" \
  --queries "marzenie OR rzuciłem OR startup"

# Mark an item as NO_DATA (attempted search, but unmentioned):
python3 project/scripts/checklist.py -C <chat_id> --update leis_sports_exercise_habits \
  --set-status no_data \
  --notes "Queried -s 'sport OR siłownia' --semantic 'exercise': 0 results" \
  --queries "sport OR siłownia OR trening"

# Batch update multiple items:
python3 project/scripts/checklist.py -C <chat_id> --batch-update item1 item2 \
  --set-status no_data --notes "Queried terms: 0 mentions found"

# PIPELINE BLOCKING GATE CHECK (Exit 0 = Passed, Exit 1 = Blocked):
python3 project/scripts/checklist.py --check -C <chat_id>

# SAFETY WAIVER / DISABLING (For ad-hoc queries, partial tasks, or Mode A):
python3 project/scripts/checklist.py -C <chat_id> --waive --reason "Ad-hoc Q&A task"
# (Or via query_chat):
python3 project/scripts/query_chat.py -C <chat_id> --waive-checklist --reason "Ad-hoc Q&A task"

# RE-ENABLE CHECKLIST (When comprehensive Mode B profiling is active):
python3 project/scripts/checklist.py -C <chat_id> --enable
```

---

## 5. Query Toolchain Recipes (`query_chat.py`)

All searches operate against the analytical SQLite database (default: `chat.db` in workspace root):

### 5.1 Lexical Keyword Search (`-s` / `-st`)
```bash
# Search individual messages for domestic order keywords:
python3 project/scripts/query_chat.py --db chat.db -s "sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać"

# Search full dialogue threads for work ethic and leadership:
python3 project/scripts/query_chat.py --db chat.db -st "praca OR szef OR nadgodziny OR leniuchować OR obijać OR awans OR lider"

# Scope search to a specific interlocutor / chat:
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" -s "pieniądze OR oszczędzać OR kredyt"
```

### 5.2 Semantic Vector Search (`--semantic`)
```bash
# Probe unfulfilled ambitions and abandoned dreams semantically:
python3 project/scripts/query_chat.py --db chat.db --semantic "unfulfilled ambitions, abandoned dreams, deferred projects, regret"

# Probe attitude toward AI and automation:
python3 project/scripts/query_chat.py --db chat.db --semantic "attitude toward artificial intelligence, automation, machine learning"
```

### 5.3 Context Verification ($N-5 \dots N+5$)
Before adopting any search result as evidence, inspect surrounding context:
```bash
# Inspect the direct causal reply chain:
python3 project/scripts/query_chat.py --db chat.db -c <message_id>

# Inspect full dialogue thread transcript:
python3 project/scripts/query_chat.py --db chat.db -t <thread_id>

# Inspect local context window around a specific message:
python3 project/scripts/query_chat.py --db chat.db -f <message_id> -w 5
```

---

## 6. The Master Bilingual Probing Lexicon

Use this lookup table to target specific lifestyle, relational, and behavioral dimensions:

| Analytical Target | Polish Query Keywords (`-s`, `-st`) | English / Semantic Query Keywords (`--semantic`) | Primary Focus & Diagnostic Questions |
| :--- | :--- | :--- | :--- |
| **Domestic Order & Cleanliness** | `sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać OR myć OR zmywać OR pranie OR czysto OR brudno` | `cleaning OR mess OR clutter OR tidy OR neat OR chores OR clean apartment OR dirty dishes` | Domestic orderliness vs. chaos/mess tolerance; cleaning as stress coping; environment as psychological mirror. |
| **Altruism & Helping Others** | `pomoc OR pomóc OR pomagać OR przysługi OR wsparcie OR poradzić OR wolontariat OR bezinteresownie` | `helping others OR altruism OR favor OR assist OR support OR giving advice OR selfless` | Spontaneous prosocial helpfulness vs. transactional support, savior complex, or boundary avoidance. |
| **Friendship Cadence & Outings** | `spotkanie OR spotkać OR piwo OR kawa OR wyjście OR znajomi OR przyjaciel OR impreza OR domówka` | `meeting friends OR hangout OR coffee OR drinks OR pub OR party OR socializing` | Cadence of offline social meetings; superficial contacts vs. intimate confidants; real-life vs. digital-only interaction. |
| **Work Ethic & Diligence** | `praca OR pracować OR nadgodziny OR zapieprz OR harować OR obowiązki OR sumienny OR deadline OR awans` | `work ethic OR hardworking OR overtime OR diligent OR ambitious OR professional duty` | Conscientious grinder ("pracuś") vs. coasting, slacking ("obijanie"), or minimal viable effort. |
| **Unfulfilled Ambitions & Dropped Goals** | `marzenie OR chciałem OR planowałem OR rzuciłem OR zrezygnowałem OR nie wyszło OR startup OR studia OR żałuję` | `unfulfilled ambition OR abandoned project OR dropped out OR regret OR deferred dream OR failed plan` | Catalogue of unrealized dreams; dropped degrees/startups; open psychic wounds vs. mature mourning and recalibration. |
| **Team Player vs. Lone Wolf** | `zespół OR drużyna OR współpraca OR gracz zespołowy OR razem OR samotnik OR indywidualista` | `teamwork OR team player OR collaboration OR cooperative OR lone wolf` | Cooperative synergy and credit sharing vs. fierce autonomy, silo working, and distrust of collective efforts. |
| **Sports & Physical Activity** | `sport OR siłownia OR bieganie OR biegam OR trening OR ćwiczyć OR rower OR basen OR mecz` | `sports OR gym OR workout OR running OR fitness OR exercise OR training` | Exercise habits and athletic discipline; body image driver vs. sedentary lifestyle and physical apathy. |
| **Leisure & Hobbies** | `czas wolny OR hobby OR grać OR seriale OR czytać OR odpoczynek OR nudzi mi się` | `free time OR hobby OR gaming OR watching OR reading OR bored` | Discretionary restoration modes; passive consumption (scrolling, streaming) vs. active passions (gaming, arts, reading, tinkering). |
| **Political & Societal Views** | `polityka OR wybory OR rząd OR podatki OR partia OR państwo OR wolność` | `politics OR elections OR government OR taxes OR freedom OR laws` | Socio-political orientation; stance on governance, civic duties, liberty, tradition; empirical debate style vs. moral superiority. |
| **Vacations & Holidays** | `urlop OR wakacje OR wyjazd OR odpocząć OR plaża OR hotel OR wolne w pracy` | `vacation OR holiday OR summer trip OR resort OR time off` | Vacation structure (rigid planning vs. spontaneous drifting); psychological ability to unplug vs. persistent hyper-vigilance. |
| **AI & Modern Technology** | `AI OR sztuczna inteligencja OR ChatGPT OR model OR robot OR technologia` | `AI OR artificial intelligence OR LLM OR automation OR tech` | Early adopter vs. skeptic vs. apprehensive; daily practical workflow integration vs. resistance to technological shifts. |
| **Animals & Pets** | `pies OR piesek OR kot OR kotek OR zwierzak OR pupil OR schronisko` | `dog OR puppy OR cat OR kitten OR pet OR animal OR shelter` | Pet ownership; emotional warmth and empathy toward animals; sensory/cleanliness boundaries. |
| **Travel (Motivations & Style)** | `podróż OR zwiedzać OR samolot OR lot OR zagranica OR walizka OR wycieczka` | `travel OR trip OR flight OR abroad OR sight-seeing OR journey` | Motivations (cultural curiosity, routine escape, wanderlust) vs. committed homebody; domestic vs. international travel. |
| **Money Management & Spending** | `pieniądze OR oszczędzać OR wydać OR drogo OR tanio OR kupić OR finanse OR kredyt` | `money OR save OR spend OR budget OR splurge OR frugal OR debt` | Frugal planning and disciplined saving vs. impulsive spending and status buying; money as safety, autonomy, or guilt. |

---

## 7. Probing Workflow & Step-by-Step Procedure

1. **Initialize Checklist (Mode B only):** Run `python3 project/scripts/checklist.py --init -C <chat_id>`.
2. **Execute Targeted Queries:** Run Polish lexical (`-s` / `-st`) and English semantic (`--semantic`) searches via `query_chat.py`.
3. **Contextual Verification ($N-5 \dots N+5$):** Inspect candidate matches via `-c <id>` or `-f <id> -w 5`. Verify speaker identity and genuine intent (rule out sarcasm, pasted text, and immediate rebuttals).
4. **Update Checklist State in Database:**
   - If evidence is found: update item to `completed` with quote anchors `[#ID | YYYY-MM-DD]` and queries used.
   - If unmentioned after exhaustive searches: update item to `no_data`, logging the probe queries.
5. **Run Gate Verification:** Run `python3 project/scripts/checklist.py --check -C <chat_id>`. Ensure exit code 0 before proceeding to Step B.5.
6. **Apply Evidentiary Inclusion / Omission in Final Report:** Synthesize confirmed dimensions into the narrative report. Completely omit `no_data` dimensions without placeholder text.

---

## 8. Verification Checklist

Before completing an inquiry into lifestyle or behavioral spheres, verify:
- [ ] Was `python3 project/scripts/checklist.py --init` executed (if Mode B)?
- [ ] Were query terms executed in the appropriate language (Polish lexical `-s`/`-st`, English semantic `--semantic`)?
- [ ] Were candidate quotes verified in surrounding context ($N-5 \dots N+5$)?
- [ ] Were speaker identities disambiguated (subject vs. interlocutor vs. quoted text)?
- [ ] Were all 46 checklist items resolved (`completed` or `no_data`), and does `checklist.py --check` exit with code 0?
- [ ] Are all reported observations grounded in concrete message IDs (`[#ID | YYYY-MM-DD]`)?
- [ ] Were completely unmentioned life spheres (`no_data`) omitted from the final narrative report without placeholder boilerplates?
