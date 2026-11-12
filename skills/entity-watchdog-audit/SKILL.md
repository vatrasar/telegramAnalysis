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

### Step 2: Logical Clustering of Candidate Mentions (Supervisor Brain)
The Supervisor retrieves candidate mentions across all third-party threads:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --candidates --json
```
Using analytical reasoning, the Supervisor consolidates raw mentions into logical character clusters (e.g. mapping "Rahul", "indian guy", "tinder date" $\to$ Threads `t206660, t206661`).

### Step 3: Parallel Investigator Dispatch on Clusters (Supervisor $\to$ Up to 4 Workers)
The Supervisor invokes up to 4 parallel `entity-investigator` subagents (`Model: "flash"`):
- Each worker receives one specific character cluster and its associated thread IDs.
- Workers inspect the full thread transcripts (`query_chat.py -C <chat_id> -t <thread_id>`) or run targeted keyword probes (`-s "<keyword>"`).
- Workers verify human identity vs. bystander/noise, extract quote anchors (`[#ID | YYYY-MM-DD]`), and report back. Workers never write to SQLite.

### Step 4: Atomic Registration & IMMEDIATE Anti-Conflation Audit
1. **Atomic Registration:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> \
     --register-entity "<Name>" --role "<Role>" --desc "<Anchors & Context>"
   ```
2. **🚨 Immediate Anti-Conflation Audit:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --conflation-audit
   ```
   If any collision risk is flagged (e.g. two entities sharing a role like *sister* or trait like *Indian*):
   - **HALT immediately before deep research.**
   - Audit the colliding threads to verify separation and ensure no attributes or quotes bled between them.
   - Enforce explicit **Negative Boundaries** in `--desc`:
     ```bash
     python3 project/scripts/query_chat.py -C <chat_id> \
       --register-entity "<Name>" --desc "<Existing desc>; NOT <Other_Entity>"
     ```

### Step 5: System-1 Catch-up Sweep Scan (Gap Fill)
The Supervisor executes a fast, non-blocking sweep scan:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan --sweep
```
- Known entities are cleared in bulk (`[✓ CLEARED]`).
- Any residual threads with unmapped individuals (`unregistered_detected`) missed by extraction are surfaced and investigated.

### Step 6: Hard-Stop Gate Clearance
Verify that the gatekeeper passes:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
```
Exits with code 0 (`[✓] PASSED: 100% of third-party threads are verified`).

---

### PHASE B: Deep Salient Entity Profiling & Relational Dossiers

Once the complete entity registry is established and the Watchdog Gate is resolved:
1. **Noise Rejection:** Retain all psychologically salient figures (family, suitors, partners, close friends, superiors, therapists); discard purely transient contacts.
2. **Negative Boundary Injection:** Provide deep profilers with explicit boundaries.
3. **Wave-Based Parallel Profiling (Up to 4 Workers):** Dispatch `entity-deep-profiler` subagents to perform dual lexical (`-s`) and semantic (`--semantic`) searches.
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

# Skip false positive or episodic bystander thread (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "episodic_bystander"
```

---

## 4. Hard-Stop Blocking Gate & Downstream Prerequisites

The Entity Watchdog is a **strict programmatic prerequisite**:
1. `thread_checklist.py --init -C <chat_id>` and `checklist.py --init -C <chat_id>` verify the watchdog gate. They immediately exit with code 1 if any third-party thread remains pending or has unregistered entities detected.
2. `assemble_report.py --check-gates` verifies that all third-party threads are 100% resolved before allowing report generation.
