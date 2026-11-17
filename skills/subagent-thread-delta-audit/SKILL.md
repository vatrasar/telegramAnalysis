---
name: subagent-thread-delta-audit
description: >-
  Delegates thread delta triage and deep forensic verification to Antigravity Flash subagents. Use during post-spheres thread audits.
---

# Subagent Thread Delta Audit & Forensic Deep Dive Protocol

This skill governs the delegation of high-volume thread audits and entity verifications to Antigravity subagents using the `flash` model. It prevents main-agent context exhaustion while ensuring zero procedural shortcuts.

---

## 1. Architectural Timing & Operational Prerequisites

Subagent Thread Delta Auditing must occur **strictly after completing Step B.4 Life Spheres**:
1. **Established Baseline Prerequisite:** The Main Agent must first complete the 50-dimension Life Spheres audit (`checklist.py`), establishing a clear psychological baseline and known entity catalog.
2. **Delta Principle ($\Delta = \text{Thread} \setminus \text{Baseline}$):** A thread is only evaluated for novelty against the established baseline. Redundant threads that merely confirm known traits are formally resolved without burning deep-dive tokens.
3. **Subagent Context Isolation:** Subagents run in isolated contexts with `Model: "flash"`. Raw transcripts remain within the subagent sandbox; only concise evidence packets return to the Main Agent.

---

## 2. Phase 1: Delta Triage Subagent (Novelty vs. Redundancy - Up to 5 Threads per Worker)

### Step 1.1: Export Delta Manifest
Export pending threads with their System-1 summaries and candidate entities:
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --export-delta-manifest
```

### Step 1.2: Launch Delta Triage Subagents in Batches of 5
To maintain high precision and prevent attention degradation, slice pending threads into batches of **up to 5 threads per worker**. Invoke `thread-delta-triage` subagents in parallel using `invoke_subagent`:
- **TypeName:** `thread-delta-triage`
- **Role:** `Thread Delta Triage Evaluator (<batch_id>)`
- **Model:** `flash`
- **Prompt Structure:**
  ```text
  You are evaluating a batch of up to 5 pending dialogue threads against an established psychological baseline.

  ESTABLISHED BASELINE:
  [Insert 300-500 word synthesis of subject's known history, relationships, and defenses from 50 spheres]

  PENDING THREADS (Max 5):
  [Paste slice of up to 5 threads from --export-delta-manifest]

  TASK:
  Classify each of the 5 threads into one of two categories:
  1. REDUNDANT / CORROBORATING: Threads confirming known patterns (e.g. repeated arguments with parents, routine small talk, known partner discussions). Specify the baseline theme corroborated.
  2. NOVELTY / DEEP DIVE: Threads indicating unmapped events, acute crises, contradictory behaviors, or unrecognized external individuals.

  OUTPUT FORMAT:
  Respond with a JSON object:
  {
    "redundant": [{"thread_id": "...", "reason": "corroborating_<theme>"}],
    "novel": [{"thread_id": "...", "justification": "..."}]
  }
  ```

### Step 1.3: Formal Resolution of Redundant Threads
The Main Agent marks redundant threads using the sanctioned CLI (never raw SQL):
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --resolve-redundant <id1> <id2> ... --reason "corroborating_<theme>"
```

---

## 3. Phase 2: Forensic Deep Dive Subagent (Per Novel Thread)

For each thread identified in `novel` (typically 5–12 threads):

### Step 2.1: Launch Deep Dive Subagent
Invoke the custom Antigravity subagent using `invoke_subagent`:
- **TypeName:** `forensic-thread-investigator`
- **Role:** `Forensic Thread Investigator`
- **Model:** `flash`
- **Prompt Structure:**
  ```text
  Perform an exhaustive forensic audit on thread <thread_id> for chat <chat_id>.

  EXECUTION INSTRUCTIONS:
  1. Check audit cache first:
     python3 project/scripts/query_chat.py -C <chat_id> --is-inspected <thread_id>
     If already audited with complete coverage, review findings. If uninspected or partial, read with:
     python3 project/scripts/query_chat.py -t <thread_id> --force
  2. Verify Scaledown summary claims against verbatim text. Do NOT trust unverified summary claims.
  3. Extract 2-4 key anchored quotes in [#ID | YYYY-MM-DD] format.
  4. Adversarial Post-Check:
     python3 project/scripts/query_chat.py -C <chat_id> --anomaly-check <thread_id> --identified "<primary_finding>"
  5. If any unmapped third-party individual or relational figure is introduced, register them:
     python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name/Role>" --role "<Role>" --desc "<Context>"
  6. Update the thread checklist status:
     python3 project/scripts/thread_checklist.py -C <chat_id> --update <thread_id> --set-status completed --findings "<Dynamics>" --quotes "<Anchored quotes>" --tags "<Tags>"
  7. Return a concise (150-250 words) structured evidence summary to the supervisor.
  ```

---

## 4. Phase 3: Evidence Curation & Chapter Routing (`evidence-curator`)

Once all novel threads are audited and marked `completed`, the Supervisor dispatches the `evidence-curator` subagent:
- **TypeName:** `evidence-curator`
- **Role:** `Forensic Evidence Curator`
- **Model:** `flash`

### Step 4.1: Autonomous Sharding Invariant ($\le 5$ Items per Worker)
If completed evidence items $> 5$, the curator shards items into batches of up to 5 items and delegates evaluation to parallel helper subagents.

### Step 4.2: Evidence Valuation & Chapter Routing
For each evidence item, the curator determines value-add and records routing in SQLite:
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --route-evidence <thread_id> \
  --target-agent "<chapter-drafter|operational-playbook-architect>" \
  --target-chapter "<family|career|worldview|romantic|lifestyle|playbook>" \
  --significance "<Significance note>"
```

### Step 4.3: Dynamic Custom Section Proposal
If anomalous evidence reveals high-salience themes that exceed standard chapter schemas (e.g. secret gambling addiction, unmapped crisis, radical break), the curator proposes a dedicated custom section:
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --propose-custom-section \
  --section-title "<Title>" \
  --section-filename "03_custom_<slug>.md" \
  --section-rationale "<Rationale>" \
  --section-threads "<threads>" \
  --section-quotes "<quotes>" \
  --target-agent "chapter-drafter"
```

---

## 5. Invariants & Prohibitions

- **Prohibition on Context Flooding:** The Main Agent must NEVER sequentially dump 50+ raw transcripts into its primary context. The Main Coordinator delegates the entire Step B.4 to `thread-supervisor`.
- **Prohibition on Unverified Summaries:** Scaledown summaries are routing metadata only; no claim may appear in the final report without verbatim quoted message anchors (`[#ID | YYYY-MM-DD]`).
- **Prohibition on Ad-Hoc SQL Updates:** Marking threads completed via direct `sqlite3 "UPDATE..."` commands is strictly prohibited.
- **FRAUD Invariant: Mandatory Subagent Triage:** Closing or resolving threads as redundant without delegating the manifest to the `thread-delta-triage` subagent is strictly prohibited. A finding where all threads are classified as redundant is fully valid, but skipping evaluation constitutes investigative fraud.
