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

## 2. Pre-Flight Configuration & Startup Gate (Main Coordinator ONLY)

Before performing any ingestion, indexing, or initiating chat analysis, the Main Coordinator **MUST** run:
```bash
python3 project/scripts/setup_config.py
```
- **Main Coordinator ONLY:** Executed exactly once at session startup before initiating pipeline steps.
- **Subagent Invariant:** Subagents (supervisors, investigators, profilers, drafters, triage workers) **MUST NEVER** run `setup_config.py`. Subagents operate under the strict invariant that runtime configuration and OpenRouter connectivity have already been pre-flight verified and approved by the Main Coordinator.
- **Exit Code 0 (`SUCCESS`):** Verified. Proceed with analysis.
- **Exit Code 2 (`ACTION_REQUIRED`):** Halt immediately and prompt the user to configure `config/embeddings_config.json` with their OpenRouter API key.
- **Exit Codes 3–6 (`ERROR`):** Report exact diagnostic (401 auth, 402 credits, 404 model, 6 network) and halt.
- **Prohibition on Downstream Execution:** If exit code is non-zero, you are strictly forbidden from calling downstream analysis scripts or attempting raw data inspection.

---

## 3. Personality Profiling Pipeline Architecture

This branch is dedicated to comprehensive personality profiling and psychological dossier synthesis.

### 3.1 Incremental Chat Updates & Entity Delta Scan
When a chat is updated with new messages or threads:
1. Run ingestion & embedding update (`scripts/db_builder.py`, `scripts/vector_indexer.py --incremental`).
2. **Delta Entity Scan:** Run the entity watchdog scan ONLY on the newly arrived threads:
   ```bash
   python3 scripts/query_chat.py -C <chat_id> --watchdog-scan
   ```
   The engine automatically skips previously cleared/skipped threads using `thread_entity_audit`, auditing only the newly introduced threads to detect any new people or relation figures without re-scanning previously audited history.

---

### 3.2 Profiling Execution Workflow

#### Step B.1: Macro-Reconnaissance, System-1 Triage & Batch Enrichment
- Quantitative baselines: `query_chat.py --stats`, `--gaps` (audit duration intervals & prolonged pauses via `--min-days 7`), `--timeline`, `--burning-days`.
- Salience radars: `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
- **System-1 Screening & Scaledown Batch Enrichment:**
  1. System-1 evaluates all conversation threads for salience anomalies and third-party flags (`triage_threads.py`).
  2. Immediately following System-1 completion, the Main Coordinator runs batch enrichment:
     ```bash
     python3 project/scripts/triage_threads.py -C <chat_id> --enrich
     ```
     - **Extraction (`candidate_entities`):** Executed on all threads flagged with third parties (`mentions_third_party = 1`).
     - **Summaries (`summary_short`):** Generated for all third-party threads AND all anomaly threads.
- Always audit metrics per dyad via `-C <chat_id>`. Inspect entity baselines via `--entities` and `--descriptors`.

#### Step B.2: Entity Disambiguation & Watchdog Loop (Prerequisite)
- **Mandatory Entity Watchdog Delegation:** To protect primary context and prevent token exhaustion, the Main Agent does NOT process individual threads or register entities directly.
- Activate `entity-watchdog-audit` skill and invoke the dedicated **Entity Registry Supervisor** (`entity-supervisor`, `Model: "flash"`):
  - **Phase B.2a (Discovery & Clearance):** The Supervisor orchestrates System-1 scans and dispatches suspect threads to up to 4 parallel `entity-investigator` subagents by providing the `thread_id`, the thread `summary_short`, and the extracted `candidate_entities` (as well as known registered entities). Subagents investigate the thread autonomously (`query_chat.py -C <chat_id> -t <thread_id>`, `-s "<keyword>"`, etc.) to locate and verify entities.
  - **Thread Inspection Tracking & Discovered Facts Repository:** Reading chat logs is the most time-consuming pipeline operation. While reading threads, investigators are strictly forbidden from ignoring high-salience facts outside the entity scope (career, politics, family roots, attachment, health, addictions). Investigators return these under `discovered_facts`. The Supervisor:
    1. Marks the audited thread as inspected in SQLite: `query_chat.py -C <chat_id> --mark-inspected <thread_id> --inspected-by "entity-investigator" --stage "entity_discovery" --findings "..." --covered-spheres "<spheres>"`.
    2. Records and tags all discovered facts in the evidence repository: `query_chat.py -C <chat_id> --record-facts-batch '<json>' --fact-thread <thread_id> --discovered-by "entity-investigator"`.
    The Supervisor deduplicates characters across threads, enforces cardinality ($K=1$ vs $K \ge 2$), registers verified entities (`--register-entity`), and clears the Watchdog Gate (`--check-watchdog-gate` exits 0).
  - **Phase B.2b (Deep Relational Profiling):** The Supervisor screens the registered cast via noise rejection (retaining ALL psychologically salient figures without artificial limits), injects explicit negative boundaries, and launches wave-based parallel `entity-deep-profiler` subagents. Workers use a dual-search engine (lexical FTS + semantic role queries) to synthesize complete Relational Dossiers (`reports/<chat_id>_entities/`).
- Step B.2 is complete when the Watchdog Gate exits 0 and all salient relational dossiers are synthesized.
- *Note:* Step B.3 initialization (`checklist.py --init` and `thread_checklist.py --init`) is **programmatically blocked** until the watchdog gate returns exit code 0.

#### Step B.3: Life Spheres Baseline Investigation (`checklist.py`)
- Activate `life-spheres-investigation` skill for criteria, lexicons, and vector queries.
- Init: `python3 project/scripts/checklist.py --init -C <chat_id>` (Enforces completed Watchdog Gate)
- **Pre-Extracted Evidence First & Anti-Redundancy Mandate:**
  Before executing new queries across the chat archive, subagents (`life-sphere-investigator`) MUST run:
  ```bash
  python3 project/scripts/query_chat.py -C <chat_id> --facts-for-sphere <sphere_letter>
  python3 project/scripts/query_chat.py -C <chat_id> --inspected-threads --sphere <sphere_letter>
  ```
  Subagents immediately integrate verified pre-extracted quotes and insights into `checklist.py`. Subagents are strictly prohibited from re-reading threads already marked as inspected; queries must focus exclusively on unaddressed criteria and uninspected threads.
- **Warm-Start Context Budget (2000-Token Discipline):** The Main Agent injects prior knowledge from Phase B.2 as a foundation (capped at ~2000 tokens with explicit truncation notice pointing to `query_chat.py --entities`). Subagents use this to formulate deeper queries without re-asking basic facts, but MUST execute genuine vector and lexical searches to uncover full depth on remaining gaps.
- Audit items via primary vector search (`query_chat.py --semantic`) and targeted lexical queries (`-s`).
- Record findings: `python3 project/scripts/checklist.py -C <chat_id> --update <id> --set-status completed --notes "..." --queries "..." --semantic-queries "..."`
- **Ban on Keyword-Only `no_data`:** Concluding absence requires documented semantic vector search.
- **Subagent Delegation for Sphere Clusters:** To avoid coordinator context exhaustion across 46 spheres, delegate thematic clusters to `life-sphere-investigator` subagents (`Model: "flash"`), which execute probes and update `checklist.py` in isolated sandboxes. Workers report cross-sphere discoveries back to the Coordinator.
- Completing the 46 spheres establishes the core psychological baseline.

#### Step B.4: Subagent Thread Delta Audit & Forensic Deep Dives (`thread_checklist.py`)
- Activate `subagent-thread-delta-audit` skill.
- Init: `python3 project/scripts/thread_checklist.py --init -C <chat_id>` (Automatically inherits inspected status and findings from `inspected_threads` for threads audited in Step B.2).
- **Absolute Ban on Main Agent Context Flooding:** The Main Agent must NEVER sequentially read 50+ raw thread transcripts into its primary context window.
- **Phase 1 (Delta Triage):** Export manifest (`--export-delta-manifest`) and delegate classification to an Antigravity subagent (`Model: "flash"`, `TypeName: "thread-delta-triage"`). Resolve redundant threads formally using:
  `python3 project/scripts/thread_checklist.py -C <chat_id> --resolve-redundant <id1> <id2> ... --reason "<theme>"`
- **Anti-Fraud Invariant on Delta Triage:** The Main Agent is strictly forbidden from closing or resolving threads without delegating the manifest to `thread-delta-triage`.
- **Phase 2 (Snipers' Deep Dive with Adversarial Anomaly Post-Check):** For all novel/anomalous threads identified by triage, invoke dedicated forensic subagents (`Model: "flash"`, `TypeName: "forensic-thread-investigator"`):
  - Subagents check `--is-inspected <thread_id>` before reading; if already audited, they leverage existing findings.
  - Subagents inspect windowed snippets ($\pm 4$ turns) around the anomaly epicenter instead of reading 100 messages linearly.
  - Subagents run the **Adversarial Post-Check** (`query_chat.py -C <chat_id> --anomaly-check <id> --identified "<primary_anomaly>"`) to ensure secondary crises were not prematurely overlooked.

#### Step B.5: Mandatory Triple Hard-Stop Gate, Fact Blackboard & Evidence Ingestion
Drafting final profile chapters is **STRICTLY FORBIDDEN** until all three investigative gates pass verification (exit code 0):
```bash
python3 project/scripts/query_chat.py --check-watchdog-gate -C <chat_id>
python3 project/scripts/thread_checklist.py --check -C <chat_id>
python3 project/scripts/checklist.py --check -C <chat_id>
```
- **Fact Blackboard Generation:** Compile a dense, structured fact snapshot: `reports/<chat_id>_facts_snapshot.md` containing metrics, timeline anchors, and the Cast of Characters:
  - *Character Threshold Rule:* If $\le 50$ characters, list all with 1-line verified role/descriptor. If $> 50$, list the most salient characters and add an explicit truncation disclaimer referencing `chat_entities`.
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
