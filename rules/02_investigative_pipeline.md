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

This branch (`analiza-osobowosci`) is dedicated to comprehensive personality profiling and psychological dossier synthesis.

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
1. **Quantitative Baselines:** Run `query_chat.py -C <chat_id> --stats --gaps`, `--timeline`, `--burning-days`.
2. **Salience Radars:** Sweep `--anomalies-only`, `--emotional-peaks`, `--advice-seeking`, `--triaged-threads`.
3. **Batch Enrichment:** Main Coordinator executes enrichment on flagged threads:
   ```bash
   python3 project/scripts/triage_threads.py -C <chat_id> --enrich
   ```
   Extracts candidate entities for third-party threads and generates dense summaries for all anomaly threads.

#### Step B.2: Entity Disambiguation & Relational Dossiers (Delegated to `entity-supervisor`)
- **Mandatory Supervisory Delegation:** To protect primary context, the Main Coordinator does NOT process individual candidate mentions or register entities directly.
- Activate `entity-watchdog-audit` skill and invoke the **Entity Registry Supervisor** (`entity-supervisor`, `Model: "flash"`):
  - Manages candidate screening (`candidate-triage`), parallel snippet investigation (`entity-investigator`), thread audit caching (`--record-thread-audit`), fact persistence (`--record-facts-batch`), entity registration (`--register-entity`), and anti-conflation audits (`--conflation-audit`).
  - Oversees parallel deep relational profiling (`entity-deep-profiler`) across salient figures and the interlocutor dyad, synthesizing the Relational Dossier (`reports/<chat_id>_entities/`).
- **Prerequisite Gate:** Step B.2 is complete when `query_chat.py --check-watchdog-gate -C <chat_id>` exits with code 0. Initializing downstream checklists is programmatically blocked until this gate clears.

#### Step B.3: Life Spheres Baseline Investigation (Delegated to `sphere-supervisor`)
- **Mandatory Supervisory Delegation:** The Main Coordinator delegates Step B.3 entirely to the **Life Spheres Supervisor** (`sphere-supervisor`, `Model: "flash"`).
- Activate `life-spheres-investigation` skill.
- The Supervisor initializes `checklist.py -C <chat_id> --init`, partitions the 6 life spheres (A–F) across parallel `life-sphere-investigator` subagents, tracks progress, routes serendipitous discoveries, and ensures each investigator directly drafts its modular chapter section (`reports/<chat_id>_sections/05_<sphere_letter>_<canonical_name>.md`).
- Completing the 50 spheres establishes the empirical psychological baseline.

#### Step B.4: Subagent Thread Delta Audit & Evidence Curation (Delegated to `thread-supervisor`)
- **Mandatory Supervisory Delegation:** The Main Coordinator delegates Step B.4 entirely to the **Thread Audit Supervisor** (`thread-supervisor`, `Model: "flash"`).
- Activate `subagent-thread-delta-audit` skill.
- Init: `python3 project/scripts/thread_checklist.py --init -C <chat_id>`.
- The Supervisor exports the delta manifest, coordinates parallel `thread-delta-triage` subagents in batches of up to 5 threads to resolve redundant threads, dispatches `forensic-thread-investigator` subagents for novel/anomalous deep dives, and coordinates `evidence-curator` to route findings and propose dynamic custom sections.

#### Step B.5: Mandatory Triple Hard-Stop Gate, Fact Blackboard & Custom Plan Review (Main Coordinator ONLY)
Drafting final profile chapters is **STRICTLY FORBIDDEN** until all three investigative gates pass verification (exit code 0):
```bash
python3 project/scripts/query_chat.py --check-watchdog-gate -C <chat_id>
python3 project/scripts/thread_checklist.py --check -C <chat_id>
python3 project/scripts/checklist.py --check -C <chat_id>
```
1. **Fact Blackboard Generation:** Compile a dense, structured fact snapshot: `reports/<chat_id>_facts_snapshot.md` containing metrics, timeline anchors, and the Cast of Characters (`query_chat.py -C <chat_id> --entities`, `--descriptors`).
   - *Character Threshold Rule:* If $\le 50$ characters, list all with 1-line verified role/descriptor. If $> 50$, list the most salient characters and add an explicit truncation disclaimer referencing `chat_entities`.
2. **Review Proposed Custom Sections:** Main Coordinator reviews custom sections registered by the curator:
   ```bash
   python3 project/scripts/thread_checklist.py -C <chat_id> --list-custom-sections
   ```
   Incorporate approved custom sections into the chapter drafting roadmap for Step B.6.

#### Step B.6: Diagnostic Frameworks & Modular Dossier Assembly (Delegated to `dossier-supervisor`)
- **Mandatory Supervisory Delegation:** Following gate clearance in Step B.5, the Main Coordinator delegates Step B.6 entirely to the **Dossier Assembly Supervisor** (`dossier-supervisor`, `Model: "flash"`), passing `chat_id`, subject identifier, and approved custom sections.
- Activate `forensic-personality-frameworks` and `dossier-report-assembly` skills.
- The Supervisor dispatches parallel `chapter-drafter` supervisors (which coordinate `subsection-drafter` workers under the 20-fact clustering rule via `cluster_facts.py` and assemble chapters via `stitch_chapter.py`), integrates pre-synthesized Life Sphere sections (`reports/<subject>_sections/05_*`), drafts the Concluding Summary Matrix (`08_matrix.md`), executes editorial QA, and compiles the final deliverable via `assemble_report.py --check-gates`.
- The Supervisor delivers the compiled report receipt and executive summary to the Main Coordinator.
