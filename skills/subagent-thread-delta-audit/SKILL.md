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
1. **Established Baseline Prerequisite:** The Main Agent must first complete the 46-dimension Life Spheres audit (`checklist.py`), establishing a clear psychological baseline and known entity catalog.
2. **Delta Principle ($\Delta = \text{Thread} \setminus \text{Baseline}$):** A thread is only evaluated for novelty against the established baseline. Redundant threads that merely confirm known traits are formally resolved without burning deep-dive tokens.
3. **Subagent Context Isolation:** Subagents run in isolated contexts with `Model: "flash"`. Raw transcripts remain within the subagent sandbox; only concise evidence packets return to the Main Agent.

---

## 2. Phase 1: Delta Triage Subagent (Novelty vs. Redundancy)

### Step 1.1: Export Delta Manifest
Export pending threads with their System-1 summaries and candidate entities:
```bash
python3 project/scripts/thread_checklist.py -C <chat_id> --export-delta-manifest
```

### Step 1.2: Launch Delta Triage Subagent
Invoke the custom Antigravity subagent using `invoke_subagent`:
- **TypeName:** `thread-delta-triage`
- **Role:** `Thread Delta Triage Evaluator`
- **Model:** `flash`
- **Prompt Structure:**
  ```text
  You are evaluating a manifest of pending dialogue threads against an established psychological baseline.

  ESTABLISHED BASELINE:
  [Insert 300-500 word synthesis of subject's known history, relationships, and defenses from 46 spheres]

  PENDING THREADS MANIFEST:
  [Paste output of --export-delta-manifest]

  TASK:
  Classify every thread ID into one of two categories:
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
  1. Inspect the full raw thread:
     python3 project/scripts/query_chat.py -t <thread_id>
  2. Verify Scaledown summary claims against verbatim text. Do NOT trust unverified summary claims.
  3. Extract 2-4 key anchored quotes in [#ID | YYYY-MM-DD] format.
  4. If any unmapped third-party individual or relational figure is introduced, register them:
     python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name/Role>" --role "<Role>" --desc "<Context>"
  5. Update the thread checklist status:
     python3 project/scripts/thread_checklist.py -C <chat_id> --update <thread_id> --set-status completed --findings "<Dynamics>" --quotes "<Anchored quotes>" --tags "<Tags>"
  6. Return a concise (150-250 words) structured evidence summary to the coordinator.
  ```

### Step 2.2: Main Agent Evidence Ingestion & Synthesis
The Main Agent receives the returned evidence block, evaluates its value-add for the dossier, and synthesizes valuable findings with anchored quotes into the corresponding report chapters.

---

## 4. Invariants & Prohibitions

- **Prohibition on Context Flooding:** The Main Agent must NEVER sequentially dump 50+ raw transcripts into its primary context.
- **Prohibition on Unverified Summaries:** Scaledown summaries are routing metadata only; no claim may appear in the final report without verbatim quoted message anchors (`[#ID | YYYY-MM-DD]`).
- **Prohibition on Ad-Hoc SQL Updates:** Marking threads completed via direct `sqlite3 "UPDATE..."` commands is strictly prohibited.
- **FRAUD Invariant: Mandatory Subagent Triage:** The Main Agent is strictly forbidden from closing or resolving threads as redundant without delegating the manifest to the `thread-delta-triage` subagent. A finding where all threads are classified as redundant is fully valid and acceptable, but skipping subagent evaluation constitutes investigative fraud and immediately invalidates the dossier.
