---
name: entity-watchdog-audit
description: >-
  Supervised multi-agent candidate clustering, anti-conflation audits, and System-1 sweeps for registering
  third-party entities without context flooding.
---

# Supervised Multi-Agent Entity Watchdog & Anti-Conflation Protocol

This skill provides the operational protocol, candidate clustering flow, immediate anti-conflation audits, and System-1 sweep verification for registering third-party entities with zero context flooding and strict anti-bleeding guards.

---

## 1. Overview & Two-Tier Supervisory Architecture

In longitudinal chat archives, participants frequently discuss dozens of third-party individuals (family, suitors, coworkers, medical staff). Analyzing these sequentially through slow single-thread loops causes severe operational latency.

To maximize throughput while eliminating duplicate registrations and character conflation:
1. **Main Agent (Coordinator):** Fully delegates the entity audit milestone to the dedicated **Entity Registry Supervisor** (`entity-supervisor`).
2. **Entity Supervisor (`entity-supervisor`):** Acts as the **Single Source of Truth and Sole Write Authority**. It groups extracted candidates into logical character clusters, dispatches parallel investigator subagents, enforces immediate anti-conflation audits, and clears the watchdog gate. **The Supervisor NEVER reads raw thread transcripts directly (`-t`) — thread reconnaissance belongs strictly to `entity-investigator`.**
3. **Investigator Subagents (`entity-investigator`):** Up to 4 parallel read-only analysts. They inspect threads assigned to character clusters, verify real identity, and return structured findings. **Workers do not write to SQLite.**
4. **Immediate Anti-Conflation Guard:** The Supervisor immediately audits colliding entities (sharing names, roles, or nationalities) to prevent attribute bleeding before deep profiling.

---

## 2. The 6-Step Supervisory Watchdog Protocol

### Step 1: Bulk System-1 Screening & Scaledown Candidate Extraction
1. Verify whole-chat System-1 triage has screened all threads:
   ```bash
   python3 project/scripts/triage_threads.py -C <chat_id> --status
   ```
2. Verify batch enrichment (summary & candidate entity extraction) is complete:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --candidates
   ```

### Step 2: Candidate Screening & Logical Clustering
1. The Supervisor checks candidate mentions across third-party threads:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --candidates
   ```
2. **If Candidate Count is High (> 35 mentions):**
   The Supervisor shards candidates dynamically targeting ~25–35 candidates per subagent ($\max(2, \lceil \text{total\_candidates} / 30 \rceil)$) and dispatches lightweight `candidate-triage` screener subagents:
   - `python3 project/scripts/query_chat.py -C <chat_id> --candidates --candidates-shard <X/Y> --json`
   - Screeners separate genuine third parties from transactional noise, reporting back candidates to keep and any recurring noise words to register permanently (`--add-noise-word "<words>"`).
3. **If Candidate Count is Compact ($\le$ 35 mentions):**
   The Supervisor inspects candidates directly via `--candidates --json`.
4. **Generate Hybrid Clusters & Conflation Alerts:**
   The Supervisor runs: `python3 project/scripts/query_chat.py -C <chat_id> --suggest-clusters --json`
   This automatically forms 2–3 candidate clusters based on shared thread co-occurrence and role match, while highlighting `high_conflation_risks` to prevent accidental merges ($K=1$ vs $K \ge 2$).

### Step 3: Dynamic Parallel Investigator Dispatch on Clusters
The Supervisor invokes parallel `entity-investigator` subagents (`Model: "flash"`), dynamically scaled to the number of candidate clusters without artificial limits or wave batching:
- Each worker receives one specific character cluster (2–3 candidates) and associated thread IDs.
- **Rapid Snippet Reconnaissance Protocol:** Workers execute a single initial call:
  ```bash
  python3 project/scripts/query_chat.py -C <chat_id> -ts <tid1> -ts <tid2> ... --mentions "<Candidate_Name>"
  ```
  - Inspect Thread Audit Cache: If any thread was already inspected, cached findings and unresolved pronouns (`he/she`) are automatically displayed.
  - **Stop-When-Identified Rule:** Once identity, role, and quote anchors are established and no contradictions exist across snippets, workers **STOP** immediately without loading full transcripts.
  - **Split Entity (Anti-Homonim) Guard:** If snippets reveal contradictory roles or locations (e.g. *Kaleb coworker* vs. *Kaleb Tinder*), workers treat them as distinct individuals ($K=2$) and read only that specific thread (`-t <id> --force`).
- **Thread Audit Cache Recording:** Workers cache their findings in SQLite:
  ```bash
  python3 project/scripts/query_chat.py -C <chat_id> --record-thread-audit <thread_id> \
    --coverage full \
    --entities-detected "<Identified>" \
    --unresolved "on/he: <clues about unresolved mentions>" \
    --findings "<Summary>"
  ```
- Workers report findings to Supervisor.

### Step 4: Candidate Staging, Review & Consolidated Anti-Conflation Audit
1. **Worker Candidate Staging Protocol:**
   Workers immediately persist all identified candidate entities into SQLite staging to prevent data loss:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> \
     --stage-entity "<Canonical_Name>" --role "<Role>" \
     --desc "<Anchors & Context>" --source-thread <tid>
   ```
2. **Supervisor Staging Review & Resolution:**
   The Supervisor inspects pending proposals (`query_chat.py -C <chat_id> --pending-entities`) and resolves each proposal individually:
   - **Approve New Entity:** `query_chat.py -C <chat_id> --approve-entity <id> [--canonical-name "<Name>"]`
   - **Merge Duplicate / Alias:** `query_chat.py -C <chat_id> --merge-entity <id> --into-entity "<Target_Name>" --reason "<reason>"`
   - **Reject Noise / Bystander:** `query_chat.py -C <chat_id> --reject-entity <id> --reason "<explicit_reason>"`
3. **Ingest Discovered Facts Tagged for Downstream Specialists:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> \
     --record-facts-batch '<json_facts_array>' \
     --fact-thread <thread_id> \
     --discovered-by "entity-investigator"
   ```
4. **🚨 Consolidated Anti-Conflation Audit & Disambiguation Scans:**
   Once initial staging review is completed, run the audit across the entire cast:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit
   ```
   If any collision risk is flagged (`HIGH_RISK`):
   - Dispatch an `entity-investigator` subagent for a **Disambiguation Scan** comparing the suspect pair.
   - **If confirmed DISTINCT individuals:**
     ```bash
     python3 project/scripts/query_chat.py -C <chat_id> \
       --record-distinct-pair "<EntityA>" "<EntityB>" --reason "<evidence anchors>"
     ```
     This automatically updates notes on both entities with negative boundaries (`NOT <Other>`), marks them as `GUARDED`, and caches the pair.
   - **If confirmed SAME individual:** Merge via `--merge-entity`.

### Step 5: Gate Clearance & Verification
Verify that the gatekeeper passes:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
```
Exits with code 0 (`[✓] PASSED: Entity Discovery verified`) when 0 pending proposals remain in staging and 0 high-risk conflations exist.

---

### PHASE B: Deep Salient Entity Profiling & Relational Dossiers

Once the complete entity registry is established and the Watchdog Gate is resolved:
1. **Noise Rejection:** Retain all psychologically salient figures (family, suitors, partners, close friends, superiors, therapists, interlocutor); discard purely transient contacts.
2. **Negative Boundary Injection:** Provide deep profilers with explicit boundaries.
3. **Dynamic Parallel Profiling & Volume Ceiling:**
   - Dispatch `entity-deep-profiler` subagents in parallel (scaling directly to all salient entities).
   - **Autonomous Sharding Rule ($N \le 8$ vs. $N > 8$):**
     - When an assigned entity has $\le 8$ associated threads, the profiler investigates them directly within its context.
     - When an entity has **$> 8$ threads (8–10+ threads)** (e.g. primary romantic partners, core family members, or the Interlocutor), the profiler **MUST self-scale autonomously** by spawning worker subagents (`TypeName: "forensic-thread-investigator"`, `Model: "flash"`). Each worker audits a chronological shard of 4–5 threads, allowing the profiler to synthesize the dossier from shard summaries without primary context flooding or attention degradation.
4. **Dossier Consolidation:** Persist dossiers into `reports/<chat_id>_entities/<Entity>.md`.

---

## 3. CLI Command Reference

```bash
# Display extracted candidate entities from thread triage:
python3 project/scripts/query_chat.py -C <chat_id> --candidates
python3 project/scripts/query_chat.py -C <chat_id> --candidates --json

# Query dynamic candidate entity shard for screener subagents:
python3 project/scripts/query_chat.py -C <chat_id> --candidates --candidates-shard <X/Y> --json

# Register discovered recurring noise words (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --add-noise-word "<word1>, <word2>"

# Stage a candidate entity into staging table (Workers):
python3 project/scripts/query_chat.py -C <chat_id> --stage-entity "<Name>" --role "<Role>" --desc "<Context>" --source-thread <tid>
python3 project/scripts/query_chat.py -C <chat_id> --stage-entities-batch '<json_array>' --source-thread <tid>

# Inspect pending candidate entities in staging (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --pending-entities

# Approve, merge, or reject a staged candidate entity (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --approve-entity <staging_id> --canonical-name "<Canonical_Name>"
python3 project/scripts/query_chat.py -C <chat_id> --merge-entity <staging_id> --into-entity "<Target_Name>" --reason "<reason>"
python3 project/scripts/query_chat.py -C <chat_id> --reject-entity <staging_id> --reason "<explicit_reason>"

# Record an audited distinct entity pair with negative boundaries (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --record-distinct-pair "<EntityA>" "<EntityB>" --reason "<anchors>"

# Run immediate anti-conflation and collision audit across registered entities:
python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit
python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit --json

# Verify hard-stop gate status (exit 0 on complete, 1 on fail):
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
```

---

## 4. Hard-Stop Blocking Gate & Downstream Prerequisites

The Entity Watchdog is a **strict programmatic prerequisite**:
1. `thread_checklist.py --init -C <chat_id>` and `checklist.py --init -C <chat_id>` verify the watchdog gate (`--check-watchdog-gate`).
2. Programmatically blocks (`exit 1`) if:
   - Any candidate entity proposals in `staging_entities` remain in `pending` status.
   - Any unresolved `HIGH_RISK` collisions exist in `--conflation-audit`.
3. Passes (`exit 0`) only when all candidate proposals are resolved (approved/merged/rejected), zero conflation risks remain, and handles 0-entity chats gracefully.
4. The Supervisor NEVER executes raw thread message dumps (`-t`) or legacy thread-by-thread scans (`--watchdog-scan`). Full character discovery is driven through candidate triage, dynamic screener sharding, parallel snippet investigators, and supervised staging resolution.
