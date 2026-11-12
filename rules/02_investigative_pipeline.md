---
trigger: always_on
---

# Pipeline Execution, Investigation Architecture & Operational Modes

These rules define the technical pipeline boundaries, pre-flight configuration gate, and operational workflows distinguishing ad-hoc inquiries from comprehensive personality profiling.

---

## 1. Architectural Boundary & Stateless Agent Principle

- The `project/` directory represents the **Agent Package** (skills, rules, scripts).
- **NEVER create runtime databases (`*.db`), user secrets, or runtime artifacts inside `project/`.**
- All runtime user configuration lives in `config/` in the workspace root (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live in the workspace root (e.g. `chat.db` or `data/chat.db`).
- All processing scripts in `project/scripts/` read and write runtime state in the parent workspace root.

### 1.1 Prohibition on Ad-Hoc Python/SQLite Querying Scripts
- **Absolute Prohibition:** The agent is strictly forbidden from writing or executing ad-hoc Python one-liners (`python3 -c "import sqlite3..."`), temporary scrapers, or raw SQL scripts to query, search, or slice chat messages.
- **Sanctioned Toolchain:** All exploration, searching, sender filtering, thread reading, and context audits MUST be conducted exclusively via the sanctioned CLI toolchain (`project/scripts/query_chat.py`, `checklist.py`, `thread_checklist.py`, `assemble_report.py`).

---

## 2. Pre-Flight Configuration & Startup Gate

Before performing any ingestion, indexing, or chat analysis, the agent **MUST** run:
```bash
python3 project/scripts/setup_config.py
```
- **Exit Code 0 (`SUCCESS`):** Verified. Proceed with analysis.
- **Exit Code 2 (`ACTION_REQUIRED`):** Halt immediately and prompt the user to configure `config/embeddings_config.json` with their OpenRouter API key.
- **Exit Codes 3–6 (`ERROR`):** Report exact diagnostic (401 auth, 402 credits, 404 model, 6 network) and halt.
- **Prohibition on Downstream Execution:** If exit code is non-zero, you are strictly forbidden from calling downstream analysis scripts or attempting raw data inspection.

---

## 3. Operational Modes: Mode A (Ad-Hoc) vs. Mode B (Full Profiling)

### 3.1 Mode A: Ad-Hoc Inquiries & Fact-Checking (Default)
Triggered when the user asks specific factual questions (e.g. *"What did X say about Y?"*, *"When did event Z happen?"*, *"Compare message volume"*):
1. **Targeted Query Execution:** Run relevant `query_chat.py` calls (`-s`, `--semantic`, `--stats`, `--gaps`).
2. **Context Audit:** Audit retrieved turns ($N-5 \dots N+5$ via `--around <msg_id> -n 5` or `-c <msg_id>`).
3. **Direct Response:** Answer concisely with exact dates and message anchors (`[#ID | YYYY-MM-DD]`).
4. **Prohibitions in Mode A:** Do NOT initialize section drafts, life spheres checklist, or 8-part dossier templates.
5. **Safety Waiver Mechanism:** If an active checklist from prior sessions blocks execution, safely exempt it:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --waive-checklist --reason "Ad-hoc Q&A inquiry"
   python3 project/scripts/query_chat.py -C <chat_id> --waive-threads-checklist --reason "Ad-hoc Q&A inquiry"
   ```

---

### 3.2 Mode B: Comprehensive Personality Profiling (Explicit Request Only)
Triggered **ONLY** when the user explicitly requests an in-depth personality profile, psychological portrait, or behavioral dossier.

#### Step B.1: Macro-Reconnaissance & Anomaly Detection
- Quantitative baselines: `query_chat.py --stats`, `--gaps`, `--timeline`, `--burning-days`.
- Salience radars: `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
- Always audit metrics per dyad via `-C <chat_id>`. Inspect entity baselines via `--entities` and `--descriptors`.

#### Step B.2: Entity Disambiguation & Watchdog Loop (Prerequisite)
- **Mandatory Entity Watchdog Delegation:** To protect primary context and prevent token exhaustion, the Main Agent does NOT process individual threads or register entities directly.
- Activate `entity-watchdog-audit` skill and invoke the dedicated **Entity Registry Supervisor** (`entity-supervisor`, `Model: "flash"`):
  - **Phase B.2a (Discovery & Clearance):** The Supervisor orchestrates System-1 scans and dispatches suspect threads to up to 4 parallel `entity-investigator` subagents on focused snippets (`query_chat.py --thread-snippets <id>`). The Supervisor deduplicates characters across threads, enforces cardinality ($K=1$ vs $K \ge 2$), registers verified entities (`--register-entity`), and clears the Watchdog Gate (`--check-watchdog-gate` exits 0).
  - **Phase B.2b (Deep Relational Profiling):** The Supervisor screens the registered cast via noise rejection (retaining ALL psychologically salient figures without artificial limits), injects explicit negative boundaries, and launches wave-based parallel `entity-deep-profiler` subagents. Workers use a dual-search engine (lexical FTS + semantic role queries) to synthesize complete Relational Dossiers (`reports/<chat_id>_entities/`).
- Step B.2 is complete when the Watchdog Gate exits 0 and all salient relational dossiers are synthesized.
- *Note:* Step B.3 initialization (`checklist.py --init` and `thread_checklist.py --init`) is **programmatically blocked** until the watchdog gate returns exit code 0.

#### Step B.3: Life Spheres Baseline Investigation (`checklist.py`)
- Activate `life-spheres-investigation` skill for criteria, lexicons, and vector queries.
- Init: `python3 project/scripts/checklist.py --init -C <chat_id>` (Enforces completed Watchdog Gate)
- Audit items via primary vector search (`query_chat.py --semantic`) and targeted lexical queries (`-s`).
- Record findings: `python3 project/scripts/checklist.py -C <chat_id> --update <id> --set-status completed --notes "..." --queries "..." --semantic-queries "..."`
- **Ban on Keyword-Only `no_data`:** Concluding absence requires documented semantic vector search.
- **Subagent Delegation for Sphere Clusters:** To avoid coordinator context exhaustion across 46 spheres, delegate thematic clusters to `life-sphere-investigator` subagents (`Model: "flash"`), which execute probes and update `checklist.py` in isolated sandboxes.
- Completing the 46 spheres establishes the core psychological baseline.

#### Step B.4: Subagent Thread Delta Audit & Forensic Deep Dives (`thread_checklist.py`)
- Activate `subagent-thread-delta-audit` skill.
- Init: `python3 project/scripts/thread_checklist.py --init -C <chat_id>`
- **Absolute Ban on Main Agent Context Flooding:** The Main Agent must NEVER sequentially read 50+ raw thread transcripts into its primary context window.
- **Phase 1 (Delta Triage):** Export manifest (`--export-delta-manifest`) and delegate classification to an Antigravity subagent (`Model: "flash"`, `TypeName: "thread-delta-triage"`). Resolve redundant threads formally using:
  `python3 project/scripts/thread_checklist.py -C <chat_id> --resolve-redundant <id1> <id2> ... --reason "<theme>"`
- **Anti-Fraud Invariant on Delta Triage:** The Main Agent is strictly forbidden from closing or resolving threads without delegating the manifest to `thread-delta-triage`.
- **Phase 2 (Deep Dive):** For all novel/anomalous threads identified by triage, invoke dedicated forensic subagents (`Model: "flash"`, `TypeName: "forensic-thread-investigator"`) to inspect raw text (`query_chat.py -t <id>`), extract anchored quotes, register novel entities, and update the checklist item.

#### Step B.5: Mandatory Triple Hard-Stop Gate & Evidence Ingestion
Drafting final profile chapters is **STRICTLY FORBIDDEN** until all three investigative gates pass verification (exit code 0):
```bash
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
python3 project/scripts/thread_checklist.py --check -C <chat_id>
python3 project/scripts/checklist.py --check -C <chat_id>
```
Once all gates pass, export the complete bank of verified evidence:
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --export-evidence
```
- **Evidentiary Value-Add Invariant:** The Main Agent evaluates all verified evidence items. Whenever an item introduces an unmapped historical event, unexpected relational dynamic, coping mechanism, or emotional turning point that enriches the profile, the agent synthesizes it with exact anchored quotes (`[#ID | YYYY-MM-DD]`) into the corresponding report chapter.
- The assembly script (`assemble_report.py --check-gates`) automatically enforces all three gates before compilation.

#### Step B.6: Diagnostic Frameworks & Modular Dossier Assembly
- Activate `forensic-personality-frameworks` skill for Big Five (OCEAN) and Attachment Style rubrics.
- Activate `dossier-report-assembly` skill for the 8-component report blueprint and compilation.
- **Subagent Drafting Delegation:** Delegate drafting of substantive profile chapters to `chapter-drafter` (`Model: "flash"`), and Chapter 7 (Operational Playbook) to `operational-playbook-architect` (`Model: "flash"`). The Main Agent reviews drafts against epistemic invariants, synthesizes the Summary Matrix, and compiles via:
  ```bash
  python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
  ```
