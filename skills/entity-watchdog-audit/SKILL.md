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
2. **Entity Supervisor (`entity-supervisor`):** Acts as the **Single Source of Truth and Sole Write Authority**. It groups extracted candidates into logical character clusters, dispatches parallel investigator subagents, enforces immediate anti-conflation audits, and executes the System-1 sweep scan.
3. **Investigator Subagents (`entity-investigator`):** Parallel read-only analysts dynamically scaled to the number of candidate clusters. They inspect threads assigned to character clusters, verify real identity, and return structured findings. **Workers do not write to SQLite.**
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
2. **If Candidate Count is High (> 40 mentions):**
   The Supervisor shards candidates and dispatches lightweight `candidate-triage` screener subagents:
   - `python3 project/scripts/query_chat.py -C <chat_id> --candidates --candidates-shard <X/Y> --json`
   - Screeners separate genuine third parties from transactional noise, reporting back candidates to keep and any recurring noise words to register permanently (`--add-noise-word "<words>"`).
3. **If Candidate Count is Compact ($\le$ 40 mentions):**
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

### Step 4: Atomic Registration, Fact Ingestion & Consolidated Anti-Conflation Audit
1. **Initial Registration of All Vetted Candidates:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> \
     --register-entity "<Name>" --role "<Role>" --desc "<Anchors & Context>"
   ```
2. **Ingest Discovered Facts Tagged for Downstream Specialists:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> \
     --record-facts-batch '<json_facts_array>' \
     --fact-thread <thread_id> \
     --discovered-by "entity-investigator"
   ```
3. **🚨 Consolidated Anti-Conflation Audit (Single Pass Across All Entities):**
   Once initial vetting of candidate entities is completed, run the audit across the entire cast before deep research:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit
   ```
   If any collision risk is flagged (e.g. two entities sharing a role like *sister* or trait like *Indian*):
   - Review threads for each flagged group together to separate individuals.
   - **⚠️ Explicitly Mark Ambiguities:** If any quote, event, or trait cannot be definitively pinned to one specific person due to ambiguous pronouns, **DO NOT guess**. Explicitly record it in `--desc` as `[AMBIGUOUS ATTRIBUTION: <fact>]`.
   - Enforce explicit **Negative Boundaries** in `--desc`:
     ```bash
     python3 project/scripts/query_chat.py -C <chat_id> \
       --register-entity "<Name>" --desc "<Existing desc>; NOT <Other_Entity>; [AMBIGUOUS ATTRIBUTION: <uncertain fact>]"
     ```

### Step 5: Gate Clearance & Verification
Verify that the gatekeeper passes:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
```
Exits with code 0 (`[✓] PASSED: Entity Discovery verified`).

---

### PHASE B: Deep Salient Entity Profiling & Relational Dossiers

Once the complete entity registry is established and the Watchdog Gate is resolved:
1. **Noise Rejection:** Retain all psychologically salient figures (family, suitors, partners, close friends, superiors, therapists); discard purely transient contacts.
2. **Negative Boundary Injection:** Provide deep profilers with explicit boundaries.
3. **Dynamic Parallel Profiling:** Dispatch `entity-deep-profiler` subagents in parallel (scaling directly to all salient entities) to perform dual lexical (`-s`) and semantic (`--semantic`) searches.
4. **Dossier Consolidation:** Persist dossiers into `reports/<chat_id>_entities/<Entity>.md`.

---

## 3. CLI Command Reference

```bash
# Display extracted candidate entities from thread triage:
python3 project/scripts/query_chat.py -C <chat_id> --candidates
python3 project/scripts/query_chat.py -C <chat_id> --candidates --json

# Run immediate anti-conflation and collision audit:
python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit
python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit --json

# Run System-1 watchdog scan in full non-blocking sweep mode:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan --sweep

# Sequential scan stopping on first detection (interactive mode):
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan

# Single thread verification check:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-check <thread_id>

# Check current watchdog audit progress:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-status

# Verify hard-stop gate status (exit 0 on complete, 1 on fail):
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate

# Register a verified third-party entity (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role>" --desc "<Notes>"

# Mark a thread as inspected/read (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --mark-inspected <thread_id> --inspected-by "entity-investigator" --findings "<summary>" --covered-spheres "<e.g. B,C>"

# Batch record discovered facts into evidence repository (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --record-facts-batch '<json_array>' --fact-thread <thread_id> --discovered-by "entity-investigator"

# Skip false positive or episodic bystander thread (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "episodic_bystander"
```

---

## 4. Hard-Stop Blocking Gate & Downstream Prerequisites

The Entity Watchdog is a **strict programmatic prerequisite**:
1. `thread_checklist.py --init -C <chat_id>` and `checklist.py --init -C <chat_id>` verify the watchdog gate. They immediately exit with code 1 if any third-party thread remains pending or has unregistered entities detected.
2. `assemble_report.py --check-gates` verifies that all third-party threads are 100% resolved before allowing report generation.
