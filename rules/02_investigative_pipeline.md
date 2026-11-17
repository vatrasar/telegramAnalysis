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
  - **Phase B.2a (Discovery & Clearance):** The Supervisor groups extracted candidates into clusters of **2–3 related figures** and dispatches parallel `entity-investigator` subagents dynamically scaled to the number of candidate clusters (without artificial limits or wave batching). Subagents execute rapid snippet reconnaissance (`query_chat.py -C <chat_id> -ts <tids> --mentions "<Name>"`), leverage and update the **Thread Audit Cache** (`--record-thread-audit`), enforce the **stop-when-identified** rule without linear transcript reads, and capture shadow `he/she` clues for cross-agent collaboration.
  - **Thread Inspection Tracking & Incidental Fact Capture:** Reading chat logs is the most time-consuming pipeline operation. When investigators inspect snippets or threads, if they encounter clear, high-salience declarations about the main subject (career changes, voting, family background, attachment crises), they report them under `discovered_facts`. The Supervisor:
    1. Records thread audit caching in SQLite: `query_chat.py -C <chat_id> --record-thread-audit <thread_id> --coverage <full|partial> --entities-detected "<Identified>" --unresolved "<he/she clues>" --findings "..."`.
    2. Records and tags all discovered facts in the evidence repository: `query_chat.py -C <chat_id> --record-facts-batch '<json>' --fact-thread <thread_id> --discovered-by "entity-investigator"`.
    The Supervisor deduplicates characters across threads, enforces cardinality ($K=1$ vs $K \ge 2$), registers verified entities (`--register-entity`), executes the consolidated anti-conflation audit (`--conflation-audit`), and clears the Watchdog Gate (`--check-watchdog-gate` exits 0).
  - **Phase B.2b (Deep Relational Profiling & Autonomous Self-Scaling):** The Supervisor screens the registered cast across the full relational spectrum (positive anchors/mentors, salient antagonists like toxic bosses or workplace bullies, and **mandatorily the Interlocutor / chat partner dyad**). Exactly **one subagent per entity** (`entity-deep-profiler`) is dispatched in parallel (scaling directly to all salient entities).
    - *Subagent Autonomous Self-Scaling:* The Supervisor does NOT micromanage threads. Each profiler checks volume via `query_chat.py -C <chat_id> --shard-entity "<Name>" --batch-size 5`. If threads $\le 6$, it investigates directly; if threads $> 6$, it autonomously dispatches worker subagents (`forensic-thread-investigator`) per chronological shard, synthesizing the final Relational Dossier (`reports/<chat_id>_entities/`) from returned shard summaries.
- Step B.2 is complete when the Watchdog Gate exits 0 and all salient relational dossiers are synthesized.
- *Note:* Step B.3 initialization (`checklist.py --init` and `thread_checklist.py --init`) is **programmatically blocked** until the watchdog gate returns exit code 0.

#### Step B.3: Life Spheres Baseline Investigation & Direct Section Synthesis (`checklist.py`)
- Activate `life-spheres-investigation` skill for criteria, lexicons, and vector queries.
- Init: `python3 project/scripts/checklist.py --init -C <chat_id>` (Enforces completed Watchdog Gate)
- **Pre-Extracted Evidence First & Informed Autonomy:**
  Before executing new queries across the chat archive, subagents (`life-sphere-investigator`) retrieve tagged evidence (`--facts-for-sphere`) and review audited threads (`--inspected-threads`). If cached findings answer the question, workers avoid raw transcript re-reads; however, workers maintain full autonomy to inspect (`-ts` or `-t --force`) when verifying unread turns (especially `coverage: partial`) or extracting exact quotes.
- **Two-Tier Delegation & Direct Section Synthesis (Anti-Evidence Graveyard):**
  Each life sphere (A–F) is assigned to a dedicated subagent team. To ensure 100% of discovered evidence is embedded directly into the final deliverable rather than stranded in SQLite:
  - *Autonomous Self-Scaling:* If a sphere/cluster contains $> 6$ threads (`query_chat.py --shard-sphere <Letter>`), the investigator self-scales by dispatching worker subagents per shard.
  - As soon as a sphere's criteria are audited in `checklist.py`, the sphere investigator drafts its corresponding modular chapter section directly:
    `reports/<chat_id>_sections/05_<sphere_letter>_<sphere_name>.md`
  - Drafting immediately in the same context weaves fresh evidence, tensions, and anchored quotes (`[#ID | YYYY-MM-DD]`) directly into the final report.
- Completing the 50 spheres establishes the core psychological baseline.

#### Step B.4: Subagent Thread Delta Audit, Forensic Deep Dives & Evidence Curation (`thread_checklist.py`)
- Activate `subagent-thread-delta-audit` skill.
- Init: `python3 project/scripts/thread_checklist.py --init -C <chat_id>` (Automatically inherits inspected status and findings from `inspected_threads` for threads audited in Step B.2).
- **Mandatory Supervisory Delegation (Zero Main Coordinator Flooding):**
  To protect primary context, the Main Coordinator does NOT process individual threads or evaluate raw evidence. The Main Coordinator delegates the entire phase to the **Thread Audit Supervisor** (`thread-supervisor`, `Model: "flash"`):
  - **Phase B.4a (Delta Triage - 5 Threads per Subagent):** Supervisor exports delta manifest (`--export-delta-manifest`) and dispatches parallel `thread-delta-triage` subagents in batches of **up to 5 threads**. Resolves redundant threads formally via:
    `python3 project/scripts/thread_checklist.py -C <chat_id> --resolve-redundant <id1> <id2> ... --reason "<theme>"`
  - **Phase B.4b (Snipers' Deep Dive with Adversarial Post-Check):** For all novel/anomalous threads, Supervisor dispatches dedicated forensic subagents (`forensic-thread-investigator`):
    - Subagents inspect windowed snippets ($\pm 4$ turns), run adversarial checks (`query_chat.py --anomaly-check`), and record findings and anchored quotes (`thread_checklist.py --update <id> --set-status completed ...`).
  - **Phase B.4c (Evidence Curation, Chapter Routing & Custom Sections):** Once all threads are completed, Supervisor dispatches the **Forensic Evidence Curator** (`evidence-curator`, `Model: "flash"`):
    - *Autonomous Sharding Invariant:* If completed evidence items $> 5$, curator shards into batches of up to 5 items across parallel helper subagents.
    - *Evidentiary Value-Add & Routing:* Routes high-value evidence items directly in SQLite:
      `python3 project/scripts/thread_checklist.py -C <chat_id> --route-evidence <id> --target-agent "<chapter-drafter|operational-playbook-architect>" --target-chapter "<chapter>" --significance "..."`
    - *Dynamic Custom Sections Proposal:* If anomalous themes exceed standard templates, Curator proposes custom chapters/subsections:
      `python3 project/scripts/thread_checklist.py -C <chat_id> --propose-custom-section --section-title "..." --section-filename "03_custom_..." --section-rationale "..."`
  - Supervisor verifies `thread_checklist.py --check -C <chat_id>` exits 0 and reports completion and custom section proposals to the Main Coordinator.

#### Step B.5: Mandatory Triple Hard-Stop Gate, Fact Blackboard & Custom Plan Review
Drafting final profile chapters is **STRICTLY FORBIDDEN** until all three investigative gates pass verification (exit code 0):
```bash
python3 project/scripts/query_chat.py --check-watchdog-gate -C <chat_id>
python3 project/scripts/thread_checklist.py --check -C <chat_id>
python3 project/scripts/checklist.py --check -C <chat_id>
```
- **Fact Blackboard Generation:** Compile a dense, structured fact snapshot: `reports/<chat_id>_facts_snapshot.md` containing metrics, timeline anchors, and the Cast of Characters:
  - *Character Threshold Rule:* If $\le 50$ characters, list all with 1-line verified role/descriptor. If $> 50$, list the most salient characters and add an explicit truncation disclaimer referencing `chat_entities`.
- **Review Proposed Custom Sections:** Main Coordinator reviews custom sections registered by the curator:
  ```bash
  python3 project/scripts/thread_checklist.py -C <chat_id> --list-custom-sections
  ```
  Incorporate approved custom sections into the chapter drafting roadmap for Step B.6.
- The assembly script (`assemble_report.py --check-gates`) automatically enforces all three gates before compilation.

#### Step B.6: Diagnostic Frameworks & Modular Dossier Assembly
- Activate `forensic-personality-frameworks` and `dossier-report-assembly` skills.
- **Mandatory Supervisory Delegation (Zero Main Coordinator Flooding):**
  To protect primary context and ensure strict architectural consistency, the Main Coordinator does NOT manage individual chapter drafts or assemble the final document directly. Following gate clearance in Step B.5, the Main Coordinator delegates Step B.6 entirely to the **Dossier Assembly Supervisor** (`dossier-supervisor`, `Model: "flash"`), passing the target `chat_id`, subject identifier, and approved custom sections:
  - **Phase B.6a (Subagent Drafting Delegation & Selective Evidence Fetching):** The Supervisor dispatches parallel worker subagents (`chapter-drafter`, `Model: "flash"`) for core profile chapters (`01_dossier.md`, `02_cast.md`, `04_attachment_ocean.md`) and any approved custom sections (`03_custom_*.md`), and dispatches the **Operational Playbook Architect** (`operational-playbook-architect`, `Model: "flash"`) for Chapter 7 (`05_playbook.md`). Drafters selectively query targeted evidence using CLI filters (`--evidence-for-target` and `--facts --target-agent`).
  - **Phase B.6b (Integration, Summary Matrix & Epistemic QA):** The Supervisor integrates pre-synthesized Life Sphere sections (`reports/<subject>_sections/05_*` from Step B.3), synthesizes the Concluding Summary Matrix (`06_matrix.md`), and audits all section files against epistemic invariants (Thesis-First 4-part structure, Polish language, no Mermaid diagrams, no ASCII trees, Zero-Unanchored-Descriptor rule, anchored quotes `[#ID | YYYY-MM-DD]`).
  - **Phase B.6c (Automated Gate-Checked Assembly & Delivery):** The Supervisor executes automated compilation:
    ```bash
    python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_personality_analysis.md --check-gates
    ```
    The Supervisor verifies clean exit code 0, Table of Contents generation, and reports the final delivery receipt and executive summary back to the Main Coordinator.
