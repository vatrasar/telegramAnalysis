# Analysis Agent Operating Rules: Large-Scale Chat Ingestion

## 1. Architectural Boundary: Agent Package vs. Workspace State
- The `project/` directory is strictly the **Agent Package** (skills, rules, scripts, and static templates).
- **NEVER create runtime databases, user state, or configuration files inside `project/`.**
- All runtime user configuration lives above `project/` in `config/` (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live above `project/` (e.g. `chat.db` or `data/chat.db`).

---

## 2. Pre-Flight Configuration & User Handshake (Mandatory Startup Gate)
Before performing any ingestion, indexing, or chat analysis, the agent **MUST** run the pre-flight configuration script:
```bash
python3 project/scripts/setup_config.py
```

### HARD STOP BRAMKA BLOKUJĄCA (Zero-Assumption Rule):
If `setup_config.py` returns **ANY exit code other than 0** (e.g., Code 2, 3, 4, 5, 6):
- **ABSOLUTE PROHIBITION ON DOWNSTREAM ACTIONS:** You are strictly forbidden from calling ANY further tools or scripts (`db_builder.py`, `query_chat.py`, `vector_indexer.py`, or `read_file` on chat logs).
- **NO SILENT DOWNGRADE / NO EXECUTION BIAS:** You MUST NOT rationalize: *"I will build the database or use FTS5/BM25 while waiting for the key to save time"*. Semantic vector indexing is a mandatory requirement.
- **IMMEDIATE USER PROMPT ONLY:** Your execution must halt immediately. Your output to the user must be limited strictly to requesting the configuration/API key and waiting for their explicit response.
- **EXPLICIT OPT-OUT ONLY:** The agent may ONLY proceed without embeddings if the user explicitly instructs in plain text to run in offline / FTS5-only mode (e.g. *"proceed with FTS5 only"*).

### Action Protocols Based on Pre-Flight Result:
1. **If Exit Code 2 (`ACTION_REQUIRED`):**
   - The config file was either just generated or still contains placeholder credentials (`YOUR_OPENROUTER_API_KEY_HERE`).
   - **DO NOT proceed.** Halt execution and ask the user directly:
     > *"I have initialized your configuration file at `config/embeddings_config.json` (outside the agent package and protected by `.gitignore`). Please open it, enter your OpenRouter API key and preferred embedding model, and let me know when you're done so I can proceed."*
   - Stop and wait for user confirmation. Do not call any further tools.
2. **If Exit Code 3, 4, 5, or 6 (`ERROR`):**
   - **DO NOT guess or proceed silently.** Report the exact diagnostic error directly to the user:
     - **Code 3 (HTTP 401):** *"Authentication failed (HTTP 401). Your OpenRouter API key in `config/embeddings_config.json` appears to be invalid or expired. Please check your key at openrouter.ai/keys."*
     - **Code 4 (HTTP 402):** *"Insufficient credits (HTTP 402). Your OpenRouter account balance is empty or your key's spending limit has been reached. Please check openrouter.ai/credits."*
     - **Code 5 (HTTP 404):** *"Model not found (HTTP 404). The embedding model specified in `config/embeddings_config.json` does not exist on OpenRouter."*
     - **Code 6 (Network Error):** *"Network failure. Unable to reach `openrouter.ai`. Please check internet/proxy connectivity."*
   - Halt execution and ask the user to resolve the issue.
3. **If Exit Code 0 (`SUCCESS`):**
   - Credentials and connectivity verified. Proceed immediately to Section 3.

---

## 3. Mandatory Ingestion & Indexing Pipeline
- **NEVER load raw chat logs (>1,000 messages) directly into the model context.**
- The ingestion and indexing pipeline follows a strict 3-step sequence that must be completed before any analysis starts:

### Step 3.1: Database Ingestion (SQLite + FTS5) & Clean Slate Protocol
- **Zero Cross-Subject Contamination (Clean Slate Rule):**
  When starting an analysis for a new or different person, previous database records must **NEVER** contaminate the new analysis. The agent must:
  - **Rebuild with `--clean` (Default clean slate):**
    ```bash
    python3 project/scripts/db_builder.py rozmowy/<person>.json -o chat.db --clean
    ```
    This completely purges existing messages, threads, silence gaps, and vector embeddings, guaranteeing zero noise or historical bleed from previous subjects.
  - **OR create an isolated database per person (Preservation mode):**
    ```bash
    python3 project/scripts/db_builder.py rozmowy/<person>.json -o chat_<person>.db
    python3 project/scripts/vector_indexer.py --db chat_<person>.db --index
    ```
    And subsequently pass `--db chat_<person>.db` to all queries.
  - **Multi-File Ingestion for the Same Subject:**
    If the subject has multiple split export files (e.g., `part1.json`, `part2.json`), ingest them together in one command:
    ```bash
    python3 project/scripts/db_builder.py rozmowy/person_part1.json rozmowy/person_part2.json -o chat.db --clean
    ```
  - **STRICT PROHIBITION:** Never run single-subject psychological profiling against an uncleaned `chat.db` containing data from a different person without `--clean` or isolated database naming. Uncleaned databases pollute statistical baselines (`--stats`, `--timeline`, `--gaps`) and inject false semantic matches.

### Step 3.2: Semantic Vector Indexing (MANDATORY PREREQUISITE)
Immediately after building the database, generate vector embeddings for all conversation threads:
```bash
python3 project/scripts/vector_indexer.py --db chat.db --index
```
- **DO NOT SKIP THIS STEP.** Vector indexing converts reconstructed dialogue threads into dense semantic embeddings.
- It is a required prerequisite for `--semantic` searches and psychological concept retrieval in Phase 2.
- The agent must verify that this step completed successfully before moving to query or analysis stages.

### Step 3.3: System-1 Dialogue Thread Triage (MANDATORY PREREQUISITE)
Immediately following vector indexing, run the System-1 triage engine across all threads:
```bash
python3 project/scripts/triage_threads.py --db chat.db
```
- **DO NOT SKIP THIS STEP.** The System-1 decider screens 100% of conversation threads, pruning ~45–80% of routine logistical noise while salvaging low-volume, high-salience disclosures ("quiet disclosures", e.g. 1–2 message admissions of trauma, health crises, or breakups) that volume-based filters discard.
- It detects and indexes behavioral anomalies (`is_atypical`) and interlocutor surprise/shock (`interlocutor_surprised`), providing high-priority forensic investigative leads.

### Step 3.4: Data Exploration & Analysis via CLI
All data exploration, cross-relational mining, and quote retrieval must be performed through `project/scripts/query_chat.py` (with optional `--chat <id_or_name>` filtering) or direct SQL queries against `chat.db`.

---

## 4. Multi-Stage Investigative Protocol (Profiler Mindset)

### Stage 1: Macro-Reconnaissance & Anomaly Detection
Before reading individual quotes or forming premature psychological conclusions:
1. Run `query_chat.py --stats` to establish communication volume, balance of participation, and message verbosity.
2. Run `query_chat.py --gaps` to examine silences $>24$h and identify who maintains the relationship vs. who withdraws.
3. Run `query_chat.py --timeline` to detect phases of closeness, conflict, or emotional detachment across years.
4. Run `query_chat.py --burning-days` to isolate statistically anomalous peak intensity days ($\mu + 2\sigma$).
5. Run `query_chat.py --triage-status` to inspect the macro reduction report, noise elimination rate, and category distribution.
6. Run `query_chat.py --anomalies-only` to review the highest-priority behavioral anomalies and interlocutor shocks.
7. Run `query_chat.py --triaged-threads` (or `--triaged-threads --triage-category <category>`) to retrieve substantive dialogue threads, avoiding unindexed noise.

### Stage 2: Biographical Dossier & Cast of Characters
1. **Origin Story Reconstruction:** Search for autobiographical fragments across school, university, past relationships, career pivots, and formative crucibles.
2. **Negative Anchor Audit & Baseline Check (Falsification Gate):**
   - **Primary Subject:** Explicitly query for milestone boundaries and absolute declarations (e.g. *"first boyfriend/girlfriend"*, *"never dated before"*, *"didn't have [...] until"*, *"first job"*). A single negative anchor (e.g. *"I didn't have a boyfriend until 2023"*) acts as an iron-clad falsification filter that invalidates any prior dating hypotheses.
   - **Key Entities Baseline Audit:** Extend the negative anchor audit to key figures in the Cast of Characters (e.g. parents, long-term partners). Before assigning a lifelong profession or status, query their baseline state (e.g. `mother AND (work OR job OR housewife OR pracuj OR dom)`). A direct baseline statement (e.g. *"my mother is not working"*) invalidates contradictory episodic impressions.
3. **The Actuation Gate (Modality & Irrealis vs. Realis):**
   - **Strict Prohibition on Intent Extrapolation:** Verbs of modality, offers, aspirations, proposals, or desires (*"offered"*, *"wanted to"*, *"insisted on accepting"*, *"applied"*, *"planned"*, *"dreamed"*, *"almost"*, *"chciał"*, *"miał zamiar"*) must **NEVER** be converted into established biographical facts, professions, degrees, or relational statuses.
   - A status is an objective biographical fact **only** if supported by verifiable evidence of execution, duration, or ongoing practice (*"worked there for 2 years"*, *"signed the contract"*, *"came home from school shifts"*).
4. **Resolution Check Protocol:**
   - Whenever an episodic life event, major offer, or intention appears in the logs (job offer, engagement proposal, university application, planned relocation, proposed breakup), the agent **MUST** audit the aftermath/resolution:
     - Did the event actually take place, or was it blocked, rejected, abandoned, or derailed by third parties or circumstances?
     - What was the verified outcome in subsequent months or years?
5. **Relational Constellation & Entity Disambiguation (The 4-Principle Engine):**
   - **Principle A: Relational Roles vs. Demographic Attributes (The NPC Filter):**
     - Relational roles (*"sister"*, *"ex"*, *"boss"*, *"therapist"*) denote guaranteed bonds with the subject (distinguishing them from random strangers/NPCs).
     - **Bond $\neq$ Uniqueness:** A relational role guarantees a bond, but does **NOT** guarantee a 1-to-1 individual mapping (a subject can have multiple sisters simultaneously, or sequential bosses and partners across different years).
     - Demographic attributes (*"indian guy"*, *"policeman"*, *"blonde girl"*) are surface descriptors. Never promote an episodic demographic encounter (e.g. stranger at a mall, street interaction, random chatroom lurker) into the Cast of Characters. Categorize as **Episodic Bystander / NPC**.
   - **Principle B: Action/Behavioral Signature & Conversational Inertia:**
     - Within an active relational era (e.g. 2023–2024 breakup aftermath), references to generic labels (*"indian guy"*, *"that guy"*) sharing a romantic/partner behavioral signature (jealousy, commitment battles, marriage pressure, breakup aftermath) inherit the dominant partner (Hilal) via Conversational Inertia at **O(1) zero token overhead**.
     - An interaction lacking romantic signature (e.g. passive listener on a chat in 2020) does not strictly exclude the partner, but constitutes **Lack of Evidentiary Proof**—it must never be used to anchor a romantic relationship span without explicit identity confirmation.
   - **Principle C: Cardinality State Machine ($K=1$ vs. $K \ge 2$) & Role Containers:**
     - *Uniqueness Assumption ($K=1$):* If only one person is known in a relational role across the entire archive (e.g. subject explicitly has only one sister), map directly to that person. Do not create artificial unresolved overhead.
     - *Concurrent Multi-Entity Collision ($K \ge 2$, e.g. Multiple Sisters / Multiple Peters):* If multiple individuals hold the same role simultaneously (e.g. one sister married in London, another aged 12), a bare mention (*"my sister"*) CANNOT be mapped to an individual without a distinguishing anchor (name, age, city, topic continuity). Route to a collective role container (e.g. `Sister_Unresolved`).
     - *Sequential Roles Across Timelines (e.g. Bosses, Therapists, Partners):* A role like *"my boss"* changes over time across career pivots. It maps to a specific person ONLY when grounded in the chronological employment timeline (e.g. Boss at Company A in 2021 vs. Boss at Company B in 2023). If the employer context is ambiguous, route to `Boss_Unresolved`.
     - *Container-Level Psychological Analysis:* To analyze emotional dynamics (authority conflict with bosses, sibling rivalry), the exact individual identity is often secondary; analyze the behavior at the container level without falsifying individual biographies.
   - **Principle D: Proportional Verification (The Materiality Principle):**
     - **The Golden Test:** *"Does attributing this action/event to Person B instead of Person A alter the meaning, gravity, or analytical takeaway?"*
     - **Low-Stakes (0 tokens wasted):** Generic lifestyle habits, minor daily moods, ambient background activities (*"watching a movie with indian guy"*, *"bored on discord with friend"*). If the true identity has zero bearing on the psychological insight about the subject, DO NOT launch identity queries. Treat as generic "friend/partner" without burning tokens.
     - **High-Stakes (Mandatory Verification Gate):** Targeted identity verification is strictly required whenever attributing any **consequential or high-gravity event**, including:
       1. **Biographical Milestones & Spans (The Span Claim Gate):** Start/end dates, relationship durations, formal bond status.
       2. **High-Gravity & Consequential Actions:** Crimes, violence, major financial exchanges, severe betrayal, life-altering decisions, legal or physical conflicts.
       3. **Character & Relational Pathology Attributions:** Assigning toxic dynamics, manipulation, harassment, or persistent behavioral patterns to a specific person.
       4. **Core Psychological Crucibles:** Formative traumas, foundational trust fractures, and primary attachment wounds.

### Stage 3: Intensive Discussions & Life Spheres Audit
1. Audit all intensive discussions using the **3-Point Thread Inspection Method** (Trigger $\to$ Core Stances $\to$ Resolution/Exit).
2. Systematically examine the 6 core life spheres, auditing both deep psychological dynamics and practical daily lifestyle patterns:
   - **A (Social Matrix & Friends):** Presence of authentic friends vs. acquaintances, meeting cadence and frequency (offline meetups vs. online), shared social activities, altruism & helping others (prosocial assistance vs. transactional helping), loyalty vs. door-slams, envy vs. pride.
   - **B (Work, Ambition, Leadership, Plan Execution & Finances):** Work ethic ("pracuś" / diligent grinder vs. "obijanie się" / slacker / coaster), declared aspirations and long-term ambitions, **concrete catalogue of specific unfulfilled ambitions and abandoned projects** (itemizing exact dropped ventures, uncompleted degrees, postponed career pivots, and unreached goals), plan execution track record over time (systematic follow-through vs. phantom declarations, wishful thinking, and unfulfilled ambitions), team dynamics (collaborative team player vs. autonomous lone wolf), team role (natural leader/initiator vs. task executor/follower), authority relations, money management & spending psychology (frugal/disciplined saver vs. lavish spendthrift / impulse buyer).
   - **C (Worldview, Politics & Technology):** Socio-political beliefs and ideological alignment, attitude toward Artificial Intelligence & modern technology (enthusiast, pragmatist, skeptic, fear of dehumanization), debate conduct (empirical logic vs. emotional moralism).
   - **D (Family Roots, Parental Imprints & Domestic Order):** Discipline, parentification, commitment trauma, approach to domestic order & living space (cleanliness and orderliness vs. chaos and clutter tolerance as a psychological mirror).
   - **E (Romantic Attachment & Relational Dynamics):** Attachment style, deactivating strategies, relationship patterns.
   - **F (Leisure, Sports, Travel & Animals):** How free time is spent (active vs. passive recharge), sports & physical activity (training habits, gym, active sports vs. sedentary aversion to exercise), vacation style & holiday decompression (structured vs. spontaneous, unplugging vs. work carryover), travel motivations & patterns (why and how they travel or why they avoid it), relationship with animals/pets (ownership, affection, empathy vs. aversion).
3. **Evidentiary Pruning Rule (Strict Omission of Unaddressed Topics):**
   - If a life sphere, lifestyle habit, or sub-topic (e.g. sports, pets, domestic cleaning habits, vacation style) was never mentioned or discussed in the chat archive, the agent **MUST completely omit that topic from the report**.
   - **Strict Prohibition on Placeholder Sections & Boilerplate Disclaimers:** NEVER write placeholder sections or disclaimers such as *"Brak danych na temat sportu"*, *"Temat ten nie był poruszany"*, or *"No information available"*.

### Stage 4: Forensic Dimensions & Big Five (OCEAN)
1. **Big Five Personality Model (OCEAN):** Systematically estimate trait levels across all 5 dimensions (Openness to Experience, Conscientiousness, Extraversion, Agreeableness, Neuroticism/Emotional Stability) with spectrum ratings (Low, Moderate, High), concrete conversational markers, and developmental roots. Do not assign or classify rigid 4-letter MBTI types; focus on empirical Big Five spectrums and behavioral dynamics.
2. **Forensic Probing:** Check for conspicuous absences, linguistic code-switching, temporal evolution, declared vs. actual fractures, accountability (genuine apologies vs. non-apologies), boundary testing, and late-night prefrontal fatigue ("Nighttime Truth" 23:00–04:00).

---

## 5. Disentanglement & Contextual Integrity
- Always respect the **thread anchor**: When analyzing a quote, check whether it was an answer to an explicit question or an unquoted continuation of a thought burst.
- **Never cite an isolated message in a vacuum:** Always inspect surrounding context using `query_chat.py --thread <thread_id>` or `--from-msg <id> -w 5`. Verify the stimulus, the reaction, and the aftermath.
- **Bidirectional Verification & Next-Turn Proof Procedure:**
  - **Never evaluate a message in isolation or unidirectionally.** For any pivotal claim, statement, or conflict in message $N$, the agent must execute a two-way context audit:
    1. **Antecedent Traceback (Look Back):** Query prior messages to verify whether the assertion is grounded in previously established facts, or if it is an ungrounded inference, speculation, rhetorical exaggeration, or fresh provocation.
    2. **Next-Turn Proof Procedure (Look Ahead):** Inspect subsequent turns ($N+1$ to $N+5$) to determine how the dialogue partner actually received and treated the statement. Did they confirm, accept, laugh it off, or explicitly refute it?
    3. **Immediate Rebuttal Invalidation:** If a proposition in message $N$ is immediately contradicted, corrected, or rejected by the interlocutor in turns $N+1 \dots N+5$ (e.g., *"No"*, *"Who said that"*, *"Nope, not ready"*), the agent is **strictly forbidden** from adopting the proposition in message $N$ as an established objective fact.
- **Epistemic Authority & Anti-Bothsidesism (Primary Witness vs. External Observer):**
  - **Direct Participant vs. External Spectator:** For external events occurring outside the chat (e.g., romantic encounters, third-party conflicts, family arguments), the participant who was physically present or directly involved holds primary epistemic authority over what transpired, unless contradicted by their own prior direct statements.
  - **Interlocutor as Catalyst / Stimulus:** Statements made by an external observer/interlocutor (who did not witness the event) are conversational stimuli, hypotheses, or external impressions—not empirical evidence of third-party behavior.
  - **No False Symmetry (Anti-Bothsidesism):** When an external observer posits a speculative claim about a third party and the direct participant refutes it with specific details or verbatim dialogue from that third party, do **NOT** present this as an unresolved dispute (*"Szymon believes X, but Ismi claims Y"*). Formally identify the observer's claim as an unverified speculation/stimulus that was falsified by the primary witness.
- **Entity Disambiguation Protocol (Anti-Conflation Rule):**
  - **Shared Attribute Trap:** Never conflate two distinct people simply because they share descriptive traits (e.g. same nationality, city, app, ethnicity, or generic role like "friend" / "ex").
  - Maintain clear entity profiles: `Name/Alias` + `Active Date Range` + `Context/Platform` + `True Nature of Bond` (platonic online friend vs. romantic partner).
  - Actively cross-check names before attributing actions: verify whether a story belongs to Person A or Person B.
- **Strict Timeline Bridging Ban (The Span Claim Gate):**
  - Never synthesize continuous multi-year spans (e.g. *"2020–2023"*) from disjointed mentions across years.
  - The **Span Claim Gate** enforces that whenever claiming a relationship duration or start year in a dossier, the agent MUST run a targeted query to verify continuity across intervening years or find a direct duration quote.
  - Distinguish between *"known someone casually since [Year]"* vs. *"actively dated during [Year]"*.
  - Treat isolated mentions of distant years (e.g. 2020 mentioned in a 2024 chat) as potential retrospective flashbacks (*Outliers*), requiring inspection of that specific anchor message before linking it to an ongoing entity.
- **Fact-Pinning in Biographical Dossiers:**
  - In `00_dossier_and_timeline.md` and `01_cast_of_characters.md`, every biographical milestone, relationship entry, and ex-partner summary MUST be anchored by verifiable message IDs (`[#ID | YYYY-MM-DD]`). Never draft biographical narratives from loose semantic impressions.
- **The Actuation Gate & Conditional Unrealized Trajectories:**
  - In `01_cast_of_characters.md`, maintain a strict boundary between verified biographical reality (ground truth occupation/status) and modal intentions or unfulfilled offers.
  - **Conditional Friction Recording:** Only if an unrealized trajectory, thwarted job offer, or blocked ambition actually occurred and manifested as a significant source of psychological tension, resentment, or identity conflict, record it under that character's psychological dynamics / sources of friction. Do **NOT** force this field if no such episode exists in the logs, and **NEVER** substitute an unrealized ambition for an actual occupational title.

---

## 6. Modular Drafting & Assembly Protocol
- To prevent context saturation, degradation, and file editing corruptions during deep analyses:
  1. Draft chapters in separate modular section files (e.g. `reports/<subject>_sections/01_dossier.md`, `02_cast.md`).
  2. Assemble the final unified report using the automated assembly script:
     ```bash
     python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
     ```
  3. The script verifies code fence closure and automatically generates the Table of Contents.

---

## 7. Report Standards & Delivery
- Follow the **Thesis-First Framework** defined in the personality profiling guidelines:
  - Every chapter must contain:
    - `### 📌 The Core Thesis` (2–3 bold, definitive sentences stating the insight upfront)
    - `### 🧠 In-Depth Psychological Analysis` (explicit forensic mechanisms)
    - `### 🔍 Verbatim Evidence & Case Studies` (verbatim quotes with exact `YYYY-MM-DD` dates in blockquotes)
    - `### 💡 Key Takeaway` (concise operational takeaway)
  - Mandatory Biographical Dossier & Life Timeline.
  - Mandatory Cast of Characters table and commentary.
  - Mandatory Attachment Style classification (Secure, Anxious-Preoccupied, Dismissive-Avoidant, Fearful-Avoidant).
  - Mandatory Big Five (OCEAN) profile estimation (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism/Emotional Stability). Do not assign MBTI types.
  - Mandatory **Operational User Manual** (Blind spots, triggers, unspoken need, communication protocols, statement reliability).
  - Conclude with the standard **Summary Matrix** table (including Big Five and Attachment Style).
- Benchmark quality against reference profiles in `przykłądoweAnalizy/`.

---

## 8. Output Language Standard (Default Polish Delivery)
- **Mandatory Default Output Language:** All generated personality profile reports (including intermediate modular sections) **MUST be written in Polish by default**, matching the user's primary analytical language and benchmark examples in `przykłądoweAnalizy/`.
- **On-Demand Translation:** Only if the user explicitly requests another language (e.g., *"translate this profile to English"* or *"produce in English"*) should the agent output the report in that language.
- **Specification Integrity:** All rules, skills, prompts, and technical scripts inside `project/` must remain in English.
