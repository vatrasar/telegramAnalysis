---
trigger: always_on
---

# Pipeline Execution, Data Ingestion & Investigation Architecture

These rules define the technical pipeline, toolchain execution standards, and operational workflows for ingesting, querying, and analyzing Telegram chat exports.

> [!IMPORTANT]
> **Universal Tooling vs. Task-Dependent Workflows:**
> - **Universal Core (Sections 1–3 & Section 4.1):** The data ingestion pipeline, configuration gate, and CLI query tools (`query_chat.py`) apply to **ALL** tasks—including ad-hoc user questions, fact-checking, topic searches, and quantitative inquiries.
> - **Mode A (Ad-Hoc Q&A & Targeted Inquiries):** Default mode. Query `chat.db` directly, verify context with $N-5 \dots N+5$, and answer concisely with anchored citations (`[#ID | YYYY-MM-DD]`). **Do NOT trigger full dossier generation or multi-chapter profiling.**
> - **Mode B (Comprehensive Personality Profiling):** Applies **ONLY** when the user explicitly requests a full psychological portrait, personality analysis, or behavioral dossier. Only in this mode does the agent initialize the research scratchpad (`export_scratchpad.py`), audit all 6 life spheres, evaluate Big Five traits, and execute modular section drafting with `assemble_report.py`.

---

## 1. Architectural Boundary & Stateless Agent Principle

- The `.agents/` directory is strictly the **Agent Package** (skills, rules, scripts, static templates).
- **NEVER create runtime databases (`*.db`), user state, or configuration files inside `.agents/`.**
- All runtime user configuration lives in `config/` in the workspace root (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live in the workspace root (e.g. `chat.db` or `data/chat.db`).
- All scripts in `.agents/scripts/` read and write runtime state in the workspace root.

---

## 2. Pre-Flight Configuration & Mandatory Startup Gate

Before performing any ingestion, indexing, or chat analysis, the agent **MUST** run:
```bash
python3 .agents/scripts/setup_config.py
```

### Hard Stop Blocking Gate (Zero-Assumption Rule):
If `setup_config.py` returns **ANY exit code other than 0** (e.g., Code 2, 3, 4, 5, 6):
- **Absolute Prohibition on Downstream Actions:** You are strictly forbidden from calling ANY further tools or scripts (`db_builder.py`, `query_chat.py`, `vector_indexer.py`, or `read_file` on chat logs).
- **No Silent Downgrade / No Execution Bias:** You MUST NOT rationalize using FTS5 while waiting for a key. Semantic indexing is mandatory.
- **Immediate User Prompt Only:** Halt execution immediately. Request configuration/API key from the user and stop calling tools.
- **Explicit Opt-Out Only:** May only proceed without embeddings if the user explicitly instructs in plain text to run in offline / FTS5-only mode.

### Action Protocols:
- **Code 2 (`ACTION_REQUIRED`):** Halt and ask user to fill in `config/embeddings_config.json` with their OpenRouter API key and preferred embedding model.
- **Codes 3, 4, 5, 6 (`ERROR`):** Report exact diagnostic (401 invalid key, 402 credits empty, 404 model not found, 6 network failure) and halt.
- **Code 0 (`SUCCESS`):** Verified. Proceed to Section 3.

---

## 3. Universal Ingestion & Data Query Toolchain

NEVER load raw chat logs (>1,000 messages) directly into the model context. All exploration, ad-hoc Q&A, and deep analysis operate on SQLite databases.

### Step 3.1: Database Ingestion & Smart Incremental Synchronization
```bash
python3 .agents/scripts/db_builder.py rozmowy/*.json -o chat.db
```
- **Delta Detection:** File SHA-256 hashes are verified against `source_files_manifest`. Unchanged files are skipped in 0 seconds.
- **Granular Refresh:** If a file changes, only its `chat_id` is refreshed.
- **Thread Fingerprinting (`content_hash`):** Purges orphaned vectors/triage records when threads change; preserves unchanged threads at 0 API cost.
- **Clean Rebuild (`--clean`):** Use `--clean` ONLY when the user explicitly requests a full wipe or when isolating subjects (`chat_<person>.db`).

### Step 3.2: Semantic Vector Indexing (Mandatory Prerequisite)
```bash
python3 .agents/scripts/vector_indexer.py --db chat.db --index
```
- Embeds reconstructed conversation threads into dense semantic vectors. Mandatory for `--semantic` searches and conceptual retrieval.

### Step 3.3: System-1 Dialogue Thread Triage
```bash
python3 .agents/scripts/triage_threads.py --db chat.db
```
- Screens 100% of conversation threads, filtering routine noise while salvaging quiet disclosures via Three Diagnostic Radars:
  1. *Radar 1 (Behavioral Anomalies & Interlocutor Shock):* Deviant behavior (`is_atypical`) and conversational dissonance (`interlocutor_surprised`).
  2. *Radar 2 (Acute Emotional Peaks & Dyadic Gravity):* Maximal affective amplitude (`profound_sadness`, `euphoric_joy`, `intense_rage`).
  3. *Radar 3 (Confessions & Advice Seeking):* Decision impasses, moral dilemmas, and vulnerability disclosures (`is_advice_seeking`).

### Step 3.4: Universal CLI Data Exploration (`query_chat.py`)
Query `chat.db` exclusively via `.agents/scripts/query_chat.py` or direct SQL.
Available flags for all inquiries:
- **Statistics & Chronology:** `--stats`, `--timeline`, `--gaps`, `--burning-days`, `--list-chats`, `-C <chat_id>`.
- **Targeted Retrieval:** `-s "<keyword>"` (lexical FTS5), `--semantic "<query>"` (dense vector search), `-t <thread_id>`, `-c <message_id>` (bidirectional message window).
- **Triage Radars:** `--triage-status`, `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
- **Agent Integration:** Append `--json` to any command for structured machine-readable output.

---

## 4. Operational Modes: Ad-Hoc Q&A vs. Comprehensive Profiling

### 4.1 Mode A: Ad-Hoc Questions, Fact-Checking & Targeted Inquiries (Default)
When the user asks a specific question about the chat (e.g. *"What did X say about Y?"*, *"When did they discuss Z?"*, *"Verify if event W actually happened"*, *"Compare communication volume"*):
1. **Targeted Query Execution:**
   - Execute relevant `query_chat.py` calls (combining lexical `-s` with semantic `--semantic`, or checking `--stats` / `--gaps`).
2. **Universal Epistemic Audit:**
   - Always audit retrieved messages in context ($N-5 \dots N+5$ via `-c <msg_id>`).
   - Disambiguate pronouns, check third-party boundaries, and verify whether statements were genuine or jokes/rebuttals.
3. **Direct & Concise Response:**
   - Answer the user's question directly with exact dates and verbatim message anchors (`[#ID | YYYY-MM-DD]`).
4. **Prohibitions in Mode A:**
   - **DO NOT** initialize the research scratchpad (`export_scratchpad.py`).
   - **DO NOT** create chapter drafts or section files (`reports/<subject>_sections/`).
   - **DO NOT** force an 8-part psychological dossier, Big Five ratings, or life spheres audits unless the user specifically asks for personality profiling.

---

### 4.2 Mode B: Comprehensive Personality Profiling (Explicit Request Only)
Triggered **ONLY** when the user explicitly requests an in-depth personality profile, psychological analysis, or full behavioral dossier.

#### Step B.1: Research Scratchpad & Evidence Ledger Initialization
```bash
python3 .agents/scripts/export_scratchpad.py --db chat.db -o reports/<subject>_scratchpad/
```
- Exports all triaged threads and substantive discussions into a persistent Markdown ledger (`evidence_ledger.md`) and synthesis board (`hypothesis_matrix.md`).
- **Context Protection Principle:** Prevents context window saturation, attention degradation, and amnesia of early findings.

#### Step B.2: Macro-Reconnaissance & Anomaly Detection
1. Quantitative balance: `query_chat.py --stats`, `--gaps`, `--timeline`, `--burning-days`.
2. Inspect reduction & radars: `--triage-status`, `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
3. **Anti-Simpson Relational Protocol (Multi-Chat Dyadic Normalization):**
   - In multi-chat archives sharing a subject, NEVER evaluate an interlocutor's attachment or initiative using raw global corpus shares.
   - Always audit metrics per individual chat via `Per-Chat Relational Breakdown` in `--gaps` or `In-Chat %` in `--stats` (`query_chat.py -C <chat_id> --gaps`).

#### Step B.3: Forensic Scratchpad Ingestion & Hypothesis Synthesis
1. **Partitioned Batch Auditing (Zero Context Saturation Rule):**
   - Audit threads in small batches (10–15 threads at a time) in `evidence_ledger.md` or via `query_chat.py --thread <id>`.
   - Complete Profiler Working Notes: Trigger & Context, Verbatim Anchors `[#ID | YYYY-MM-DD]`, Psychological Dynamics & Defenses, Thematic Tags (`#work`, `#attachment`, etc.), Working Hypotheses.
2. **Scratchpad-Driven Chapter Synthesis:**
   - When drafting subsequent chapters, first consult `evidence_ledger.md` and `hypothesis_matrix.md` filtered by thematic tags. Core theses must derive from pre-audited scratchpad entries.

#### Step B.4: Intensive Discussions & Life Spheres Audit
1. Audit intensive discussions using the **3-Point Thread Inspection Method** (Trigger $\to$ Core Stances $\to$ Resolution/Exit).
2. Systematically audit the 6 core life spheres:
   - **A (Social Matrix & Friends):** Authentic friends vs. acquaintances, meeting cadence, prosocial altruism, loyalty vs. door-slams.
   - **B (Work, Ambition, Plan Execution & Finances):** Work ethic, catalogue of unfulfilled ambitions/abandoned projects, follow-through record, authority relations, money psychology.
   - **C (Worldview, Politics & Technology):** Socio-political beliefs, AI & modern tech attitude, debate conduct (logic vs. moralism).
   - **D (Family Roots, Parental Imprints & Domestic Order):** Discipline, parentification, domestic order/clutter tolerance as a psychological mirror.
   - **E (Romantic Attachment & Relational Dynamics):** Attachment style, deactivating strategies, relationship patterns.
   - **F (Leisure, Sports, Travel & Animals):** Free time recharge, sports/gym habits, vacation style, travel motivations, relationship with pets/animals.

#### Step B.5: Forensic Dimensions & Big Five (OCEAN)
- Systematically rate all 5 OCEAN spectrums (Low, Moderate, High) with concrete conversational markers. Do NOT assign MBTI types.
- Forensic probing: Linguistic code-switching, declared vs. actual fractures, genuine apologies vs. non-apologies, "Nighttime Truth" (23:00–04:00).

---

## 5. Modular Drafting & Assembly Protocol (Mode B / Profiling Only)

To prevent context exhaustion and file corruption during deep profiling:
1. Draft chapters in modular section files: `reports/<subject>_sections/01_dossier.md`, `02_cast.md`, etc.
2. Assemble the final unified report using:
   ```bash
   python3 .agents/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
   ```
3. The script verifies code fence closure and automatically generates the Table of Contents.
