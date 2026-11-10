---
trigger: always_on
---

# Pipeline Execution, Investigation Architecture & Operational Modes

These rules define the technical pipeline boundaries, pre-flight configuration gate, and operational workflows distinguishing ad-hoc inquiries from comprehensive personality profiling.

---

## 1. Architectural Boundary & Stateless Agent Principle

- The `project/` (or `.agents/`) directory represents the **Agent Package** (skills, rules, scripts).
- **NEVER create runtime databases (`*.db`), user secrets, or runtime artifacts inside `project/`.**
- All runtime user configuration lives in `config/` in the workspace root (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live in the workspace root (e.g. `chat.db` or `data/chat.db`).
- All processing scripts in `project/scripts/` read and write runtime state in the parent workspace root.

---

## 2. Pre-Flight Configuration & Mandatory Startup Gate

Before performing any ingestion, indexing, or chat analysis, the agent **MUST** run:
```bash
python3 project/scripts/setup_config.py
```

### Hard Stop Blocking Gate (Zero-Assumption Rule):
If `setup_config.py` returns **ANY exit code other than 0** (e.g., Code 2, 3, 4, 5, 6):
- **Absolute Prohibition on Downstream Actions:** You are strictly forbidden from calling ANY further scripts (`db_builder.py`, `query_chat.py`, `vector_indexer.py`, or reading chat logs).
- **No Silent Downgrade:** You MUST NOT rationalize using FTS5 while waiting for a key. Semantic indexing is mandatory unless user explicitly opts out in plain text.
- **Immediate User Prompt Only:** Halt execution immediately. Request configuration/API key from the user.

### Action Protocols:
- **Code 2 (`ACTION_REQUIRED`):** Halt and ask user to fill in `config/embeddings_config.json` with their OpenRouter API key and preferred embedding model.
- **Codes 3, 4, 5, 6 (`ERROR`):** Report exact diagnostic (401 invalid key, 402 credits empty, 404 model not found, 6 network failure) and halt.
- **Code 0 (`SUCCESS`):** Verified. Proceed with analysis.

---

## 3. Operational Modes: Ad-Hoc Q&A vs. Comprehensive Profiling

### 3.1 Mode A: Ad-Hoc Questions, Fact-Checking & Targeted Inquiries (Default)
When the user asks a specific question about the chat (e.g. *"What did X say about Y?"*, *"When did they discuss Z?"*, *"Verify if event W actually happened"*, *"Compare communication volume"*):
1. **Targeted Query Execution:** Execute relevant `query_chat.py` calls (`-s`, `--semantic`, `--stats`, `--gaps`).
2. **Universal Epistemic Audit:** Audit retrieved messages in context ($N-5 \dots N+5$ via `--around <msg_id> -n 5` or `-c <msg_id>`). Apply the Anti-Snippet Ingestion Rule and the Thread Boundary Fallback Protocol. Disambiguate pronouns, check third-party boundaries, and verify intent.
3. **Direct & Concise Response:** Answer directly with exact dates and verbatim message anchors (`[#ID | YYYY-MM-DD]`).
4. **Prohibitions in Mode A:**
   - **DO NOT** initialize the research scratchpad (`export_scratchpad.py`).
   - **DO NOT** create chapter drafts or section files (`reports/<subject>_sections/`).
   - **DO NOT** initialize or enforce the life spheres checklist (`checklist.py`).
   - **DO NOT** force an 8-part psychological dossier, Big Five ratings, or life spheres audits unless the user specifically asks for personality profiling.
5. **Safety Waiver Mechanism for Ad-Hoc / Partial Tasks:**
   If the database already contains an active checklist (e.g. from a prior session or ingestion) and the task does not require life spheres profiling, the agent can explicitly waive/disable the checklist for safety:
   ```bash
   python3 project/scripts/checklist.py -C <chat_id> --waive --reason "Ad-hoc task: Q&A inquiry"
   # or via query_chat:
   python3 project/scripts/query_chat.py -C <chat_id> --waive-checklist --reason "Ad-hoc task: Q&A inquiry"
   ```
   This immediately marks all pending items as `not_applicable` and records the exemption in SQLite metadata, ensuring the agent is not blocked by pipeline gates.

---

### 3.2 Mode B: Comprehensive Personality Profiling (Explicit Request Only)
Triggered **ONLY** when the user explicitly requests an in-depth personality profile, psychological analysis, or full behavioral dossier. Execute this systematic 5-step workflow:

#### Step B.1: Research Scratchpad & Evidence Ledger Initialization
```bash
python3 project/scripts/export_scratchpad.py --db chat.db -o reports/<subject>_scratchpad/
```
- Exports all triaged threads into a persistent Markdown ledger (`evidence_ledger.md`) and synthesis board (`hypothesis_matrix.md`) to prevent context window saturation.

#### Step B.2: Macro-Reconnaissance & Anomaly Detection
1. Quantitative balance: `query_chat.py --stats`, `--gaps`, `--timeline`, `--burning-days`.
2. Inspect diagnostic radars: `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
3. **Anti-Snippet Ingestion Guard:** Treat all radar hits strictly as hypothesis cues. Never cite or draft from a triage preview without full contextual audit via `query_chat.py -t <id>` or `query_chat.py --around <msg_id> -n 5`.
4. **Anti-Simpson Relational Protocol:** In multi-chat archives, always audit metrics per individual dyad via `Per-Chat Relational Breakdown` in `--gaps` (`query_chat.py -C <chat_id> --gaps`).
5. **Entity & Role Baseline Inspection:** Inspect registered entities and descriptors for the target chat via `query_chat.py -C <chat_id> --entities` and `--descriptors`. If a chat file was refreshed or modified, review any descriptors flagged with `needs_recheck = 1`.

#### Step B.3: Forensic Scratchpad Ingestion & Hypothesis Synthesis
- Audit threads in small batches (10–15 threads at a time) in `evidence_ledger.md` or via `query_chat.py -t <id>`.
- **Thread Boundary Fallback Protocol:** If an analyzed message is near thread start/end or in a single-message thread, invoke `query_chat.py --around <id> -n 5` to inspect chronological before/after turns across thread lines.
- **Bare-Pronoun Search Attribution Ban:** Never attribute an action/trait from a search hit with a bare pronoun without checking $N-5 \dots N$ for the proper noun antecedent.
- **Lazy On-Demand Cardinality Audit:** When encountering any relational role or descriptor (*"sister"*, *"ex"*, *"US guy"*), perform an on-demand cardinality check (`query_chat.py -C <chat_id> --audit-descriptor "<term>"`) before assigning traits.
- **Third-Party Watchdog Verification:** For complex multi-party threads, apply the System-1 Watchdog loop to ensure no secondary entities were overlooked.
- Cross-examine words vs. actions across the longitudinal timeline.

#### Step B.4: Intensive Discussions & Life Spheres Audit
- Audit substantive debates using the 3-Point Thread Inspection Method (Trigger $\to$ Peak $\to$ Exit).
- **Mandatory Skill Activation:** Activate the `life-spheres-investigation` skill to retrieve forensic probing criteria and the master bilingual lexicon across all 6 life spheres.
- **Mandatory Database Checklist Initialization:**
  Initialize the complete 46-item forensic life spheres checklist in SQLite:
  ```bash
  python3 project/scripts/checklist.py --init -C <chat_id>
  ```
- **Systematic Probing & Status Resolution Protocol:**
  The agent must audit every item across all 6 spheres and record the investigative outcome in `chat.db`:
  - *Evidence Found:* Mark as `completed` with findings and citation anchors:
    ```bash
    python3 project/scripts/checklist.py -C <chat_id> --update <item_id> --set-status completed --notes "Identified uncompleted IT pivot [#1234 | 2021-03-04]" --queries "marzenie OR rzuciłem OR startup"
    ```
  - *Probed but Absent (No Data):* If lexical and semantic searches yield no relevant mentions, **the agent MUST explicitly record the probe attempt** in the database as `no_data`:
    ```bash
    python3 project/scripts/checklist.py -C <chat_id> --update <item_id> --set-status no_data --notes "Queried -s 'sport OR siłownia' --semantic 'exercise': 0 mentions found" --queries "sport OR siłownia"
    ```
  - *Batch Updates:* Rapidly reconcile multiple audited dimensions via:
    ```bash
    python3 project/scripts/checklist.py -C <chat_id> --batch-update item1 item2 --set-status completed --notes "..."
    ```
- **Hard Stop Blocking Gate before Step B.5 (100% Resolution Rule):**
  The agent is **STRICTLY FORBIDDEN** from moving to Step B.5 (Dossier Assembly) or drafting final profile chapters until all 46 items are resolved (0 `pending` items remaining). Verify via:
  ```bash
  python3 project/scripts/checklist.py --check -C <chat_id>
  ```
  If `checklist.py --check` exits with code 1 (`PENDING_ITEMS_REMAIN`), review the printed list of pending items, execute targeted queries for each, and resolve their status before proceeding.

#### Step B.5: Diagnostic Frameworks & Modular Dossier Assembly
- **Mandatory Skill Activation:** Activate `forensic-personality-frameworks` for Big Five (OCEAN) conversational markers and Attachment Style classification.
- **Mandatory Skill Activation:** Activate `dossier-report-assembly` for the 8-component report blueprint, Cast of Characters schema, Operational Playbook, Summary Matrix template, and compilation using:
  ```bash
  python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
  ```
