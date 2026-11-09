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

### Step 3.1: Database Ingestion (SQLite + FTS5) & Smart Incremental Synchronization
- **Smart Incremental Protocol (Default Mode):**
  By default, `db_builder.py` manages incremental synchronization with automatic delta detection and zero-overhead caching:
  ```bash
  python3 project/scripts/db_builder.py rozmowy/*.json -o chat.db
  ```
  - **Manifest Delta Check:** The engine verifies file SHA-256 hashes against `source_files_manifest`. Unchanged files are skipped entirely in 0 seconds.
  - **Granular Scoped Ingestion:** If a file has new or modified messages, only that specific chat (`chat_id`) is refreshed. Unmodified chats in the database are left 100% untouched.
  - **Content-Hash Caching (`content_hash`):** Every reconstructed thread receives a SHA-256 fingerprint.
  - **Automated Orphan & Stale Purge (Garbage Collection):** Any vectors or triage records belonging to deleted threads or threads whose `content_hash` changed are automatically purged. Unchanged threads retain their existing embeddings and triage verdicts, incurring **0 API token cost**.
- **Multi-File & Multi-Chat Ingestion:**
  If a subject has split export files or multiple chats, ingest them together:
  ```bash
  python3 project/scripts/db_builder.py rozmowy/person_part1.json rozmowy/person_part2.json -o chat.db
  ```
- **Isolated Database Per Person (Recommended for Independent Profiling):**
  When analyzing distinct individuals where total database separation is desired:
  ```bash
  python3 project/scripts/db_builder.py rozmowy/<person>.json -o chat_<person>.db
  python3 project/scripts/vector_indexer.py --db chat_<person>.db --index
  ```
- **Explicit Hard Reset (`--clean`):**
  Use `--clean` ONLY when the user explicitly asks for a complete wipe from scratch or when a total database rebuild is required:
  ```bash
  python3 project/scripts/db_builder.py rozmowy/<person>.json -o chat.db --clean
  ```

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
- It deploys **Three Core Diagnostic Radars**:
  1. **Radar 1 (Behavioral Anomalies & Interlocutor Shock):** Detects deviant behavior (`is_atypical`) and conversational dissonance where the partner calls out unexpected behavior (`interlocutor_surprised`).
  2. **Radar 2 (Acute Emotional Peaks & Dyadic Gravity):** Flags moments of maximal affective amplitude (`emotional_peak`: `profound_sadness`, `euphoric_joy`, `intense_rage`), capturing both direct speaker affect and subtle flat-affect disclosures revealed through interlocutor grief, deep consoling, or condolences.
  3. **Radar 3 (Confessions & Advice Seeking):** Isolates moments where the subject suspends defenses to seek advice on life/moral dilemmas or declare intimate confessions (`is_advice_seeking`).

### Step 3.4: Research Scratchpad & Evidence Ledger Initialization (MANDATORY PREREQUISITE)
Immediately following System-1 triage, initialize the file-based research scratchpad:
```bash
python3 project/scripts/export_scratchpad.py --db chat.db -o reports/<subject>_scratchpad/
```
- **DO NOT SKIP THIS STEP.** This exports all triaged threads (Radars 1–3, high-salience events) and top substantive/intensive discussions into a structured, persistent Markdown ledger (`evidence_ledger.md`) and a cross-cutting thematic synthesis board (`hypothesis_matrix.md`).
- **Context Protection Principle:** Processing hundreds of anomalies, emotional peaks, and dense discussions directly in the LLM context window causes context saturation, attention degradation ("lost in the middle"), and amnesia of early findings. The scratchpad acts as persistent, externalized working memory.

### Step 3.5: Data Exploration & Analysis via CLI
All data exploration, cross-relational mining, and quote retrieval must be performed through `project/scripts/query_chat.py` (with optional `--chat <id_or_name>` filtering) or direct SQL queries against `chat.db`.

---

## 4. Multi-Stage Investigative Protocol (Profiler Mindset)

### Stage 1: Macro-Reconnaissance & Anomaly Detection
Before reading individual quotes or forming premature psychological conclusions:
1. Run `query_chat.py --stats` to establish communication volume, balance of participation, thread initiation, and message verbosity.
2. Run `query_chat.py --gaps` to examine silences $>24$h and identify who maintains the relationship vs. who withdraws.
3. Run `query_chat.py --timeline` to detect phases of closeness, conflict, or emotional detachment across years.
4. Run `query_chat.py --burning-days` to isolate statistically anomalous peak intensity days ($\mu + 2\sigma$).
5. Run `query_chat.py --triage-status` to inspect the macro reduction report, noise elimination rate, and category distribution.
6. **Deploy the Three Diagnostic Radars:**
   - Run `query_chat.py --anomalies-only` to review behavioral deviations and partner shock.
   - Run `query_chat.py --emotional-peaks` (with optional `--peak-type profound_sadness | euphoric_joy | intense_rage`) to audit emotional valleys, grief, and affective peaks.
   - Run `query_chat.py --advice-seeking` to inspect moments of internal conflict, moral dilemmas, and vulnerability disclosures.
7. Run `query_chat.py --triaged-threads` (or `--triaged-threads --triage-category <category>`) to retrieve substantive dialogue threads, avoiding unindexed noise.

> [!WARNING]
> **Anti-Simpson Relational Protocol (Multi-Chat Dyadic Normalization):**
> Conversational initiative, thread starting, and silence reconnection are **dyadic interpersonal dynamics**, not universal subject constants.
> In archives with multiple chat files sharing a primary subject:
> - **NEVER** evaluate an interlocutor's attachment or conversational initiative using raw global corpus shares (`Global %` or flat corpus percentages), which suffer from Simpson's paradox (an interlocutor present in only 1 of 5 chats mathematically appears to have only ~10-20% global share despite 50/50 balance in their relationship).
> - **Always audit metrics per individual chat** via the `Per-Chat Relational Breakdown` in `--gaps`, `In-Chat %` in `--stats`, or filtered queries (`query_chat.py -C <chat_id> --gaps`). Relational conclusions must reflect the specific dyad.

### Stage 1.5: Forensic Scratchpad Ingestion & Hypothesis Synthesis (The Working Ledger)
Before drafting narrative chapters or biographical dossiers, the agent audits high-salience threads and populates `reports/<subject>_scratchpad/evidence_ledger.md`:
1. **Partitioned Batch Investigation (Zero Context Saturation Rule):**
   - The agent inspects threads in small, partitioned batches (e.g. 10–15 threads at a time), either reviewing them directly in `evidence_ledger.md` or via `query_chat.py --thread <id>`.
   - For each audited thread, the agent fills out the **Profiler Working Notes** template directly in `evidence_ledger.md`:
     - `Trigger & Context:` What provoked the exchange? (look back $N-5$).
     - `Verbatim Anchors:` Record exact high-value quotes with message IDs `[#ID | YYYY-MM-DD]`.
     - `Psychological Dynamics & Defenses:` Document underlying psychological drivers, ego defenses, unconscious fears, and relational stances.
     - `Thematic Tags:` Assign categorical tags (e.g., `#work`, `#attachment`, `#defense_mechanism`, `#family`, `#money`, `#unspoken_need`).
     - `Working Hypotheses:` Formulate preliminary hypotheses connecting this interaction to other life patterns.
   - **Context Reset Hygiene:** Because all findings, quotes, and hypotheses are permanently recorded in `evidence_ledger.md` on disk, the agent does NOT need to hold all threads in memory. Context can be refreshed safely without losing a single insight.
2. **Hypothesis Matrix Consolidation:**
   - Summarize cross-cutting findings into `reports/<subject>_scratchpad/hypothesis_matrix.md`, mapping emerging patterns to specific report chapters (Spheres A–F, OCEAN, Operational Manual).
3. **Scratchpad-Driven Chapter Synthesis Rule:**
   - When drafting subsequent chapters (Stages 2–4), the agent **must first consult the completed `evidence_ledger.md` and `hypothesis_matrix.md`**, filtering by corresponding thematic tags.
   - Core chapter theses (`### 📌 The Core Thesis`) and case study evidence must be derived directly from the pre-audited scratchpad entries, guaranteeing that every significant anomaly, emotional peak, and intensive exchange feeds into the final portrait.
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
- **Mandatory Bidirectional Context Audit (Unconditional $N-5$ to $N+5$ Rule):**
  - **Zero-Loophole Requirement:** This audit applies to **EVERY** message from which the agent derives an analytical conclusion, infers a personality trait, or plans to cite in the report. It applies unconditionally, regardless of message length (from 1 word or 1 sentence to multi-paragraph essays) or domain (routine lifestyle habits, domestic chores, emotional confessions, ideological debates, and conflicts alike).
  - Before utilizing message $N$ as analytical evidence, the agent **MUST** inspect an operational window of at least 5 messages backward ($N-5$ to $N$) and 5 messages forward ($N+1$ to $N+5$):
    1. **Antecedent Traceback (Look Back $N-5 \dots N$):**
       - **Stimulus & Topic Anchor:** Determine what question, event, or conversational prompt triggered the message.
       - **Lead-In & Pasted Text Detection:** Check whether preceding messages announced pasted or quoted third-party content (e.g., *"look what he wrote"*, *"his answers"*, *"us guy"*, *"he sent me this"*, *"forwarding"*).
       - **Sarcasm & Irony Verification:** Actively verify whether the statement is genuine or represents sarcasm, dry humor, mocking mimicry, or banter established in prior turns.
    2. **Next-Turn Proof Procedure (Look Ahead $N+1 \dots N+5$):**
       - Inspect how the interlocutor received and treated the statement. Did they validate it, accept it, laugh it off, expose it as a joke, or explicitly correct/rebut it?
       - **Immediate Rebuttal Invalidation:** If a proposition in message $N$ is immediately contradicted, corrected, or rejected by the interlocutor in turns $N+1 \dots N+5$ (e.g., *"No"*, *"Who said that"*, *"Nope, not ready"*), the agent is **strictly forbidden** from adopting the proposition in message $N$ as an established objective fact.
- **Semantic Author vs. Transport Sender (Caution & Authorship Verification):**
  - **Transport Channel Principle:** The `sender` field in the chat database indicates strictly who **physically pressed Enter** on their device, NOT necessarily the author of the text.
  - **Mandatory Authorship Verification:** The agent must exercise heightened caution and verify that the sender is genuinely speaking about their own personal life, habits, and views, rather than forwarding, pasting, or quoting third-party texts (e.g., ex-partners' messages, questionnaires, emails, articles).
- **Thesis Corroboration & Anti-"Eureka!" Sanity Check:**
  - **Prohibition of Premature Closure:** Discovering a single matching quote that aligns with a desired report category or trait (e.g., domestic order, cleanliness, neuroticism) is merely a preliminary hypothesis, never a proven conclusion.
  - **Active Search for Corroboration & Baseline Consistency:** The agent must attempt to find additional evidence in the text and verify that the proposed thesis does not contradict the subject's overall documented lifestyle and baseline demeanor (e.g., asserting a "pedantic domestic cleanliness rage" based on a single quote when the subject's overarching baseline is documented as slow-living and actively avoiding troublesome chores).
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
  - Mandatory Cast of Characters 3-column table (`Postać / Rola`, `Identyfikacja i Status`, `Główne Motywy i Dynamika Relacyjna`) and commentary.
  - Mandatory Attachment Style classification (Secure, Anxious-Preoccupied, Dismissive-Avoidant, Fearful-Avoidant).
  - Mandatory Big Five (OCEAN) profile estimation (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism/Emotional Stability). Do not assign MBTI types.
  - Mandatory **Operational User Manual** (Blind spots, triggers, unspoken need, communication protocols, statement reliability).
  - Conclude with the standard **Summary Matrix** table (including Big Five and Attachment Style).
- **Strict Prohibition on Mermaid Diagrams, Visual Graphs & ASCII Code-Block Timelines:**
  - **NEVER** generate mermaid code blocks (````mermaid```), flowcharts, or graphical node diagrams under any circumstances.
  - **NEVER** generate ASCII art pseudo-timelines or tree drawings using pipes (`│`, `├──`, `└──`) inside monospace code blocks (` ``` `). They break text wrapping, degrade readability, and ruin document typography.
  - **Timeline Formatting Standard (Chronological Bullet Flow):** Format all chronological lifelines and biographical timelines strictly as **clean Markdown structured bullet hierarchies**:
    - Top level: `* **[Year / Date Span] — [Phase or Formative Theme Title]**`
    - Sub-bullets: indented bullet points detailing key events, psychological implications, and fact-pinning anchors (`[#ID | YYYY-MM-DD]`).
  - Represent all relational networks, cognitive architectures, and behavioral loops strictly using clean Markdown tables, structured bullet hierarchies, and analytical prose.
- Benchmark quality against reference profiles in `przykłądoweAnalizy/`.

---

## 8. Output Language Standard (Default Polish Delivery)
- **Mandatory Default Output Language:** All generated personality profile reports (including intermediate modular sections) **MUST be written in Polish by default**, matching the user's primary analytical language and benchmark examples in `przykłądoweAnalizy/`.
- **On-Demand Translation:** Only if the user explicitly requests another language (e.g., *"translate this profile to English"* or *"produce in English"*) should the agent output the report in that language.
- **Specification Integrity:** All rules, skills, prompts, and technical scripts inside `project/` must remain in English.
