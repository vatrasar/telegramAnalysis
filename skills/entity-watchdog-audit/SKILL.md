---
name: entity-watchdog-audit
description: >-
  Supervised multi-agent System-1 cursor and parallel snippet audit for identifying and registering
  third-party entities without context flooding or duplicity.
---

# Supervised Multi-Agent Entity Watchdog & Verification Loop

This skill provides the operational protocol, System-1 gatekeeper checks, and two-tier supervisory hierarchy for identifying and registering third-party entities across conversation threads with zero context flooding and strict anti-duplication guards.

---

## 1. Overview & Two-Tier Supervisory Architecture

In longitudinal chat archives, participants frequently discuss dozens of third-party individuals (family, suitors, coworkers, medical staff). Analyzing these sequentially through the Main Agent causes severe context exhaustion and operational latency.

To maximize throughput while eliminating duplicate registrations:
1. **Main Agent (Coordinator):** Fully delegates the entity audit milestone to the dedicated **Entity Registry Supervisor** (`entity-supervisor`).
2. **Entity Supervisor (`entity-supervisor`):** Acts as the **Single Source of Truth and Sole Write Authority**. It runs System-1 scans, detects suspect threads, extracts focused snippets, and dispatches parallel investigator subagents.
3. **Investigator Subagents (`entity-investigator`):** Up to 4 parallel read-only snippet analysts. They inspect $\pm 4$ turns around Scaledown candidate mentions (`candidate_entities`), verify context and rebuttals, and return structured findings. **Workers do not write to SQLite.**
4. **Deduplication & Registration:** The Supervisor consolidates findings from all concurrent workers, merges overlapping character references, verifies cardinality, and performs atomic database registrations.

---

## 2. The 5-Step Supervisory Watchdog Protocol

### Step 1: System-1 Gatekeeper Check (Supervisor)
For threads flagged with `mentions_third_party = 1`:
- System 1 checks the thread transcript against currently registered entities $S$:
  *"Does this conversation thread introduce or discuss ANY NEW, UNKNOWN PERSON not accounted for in S?"*
- **Outcome NO (0):** Thread contains only known entities. It is marked `cleared` automatically. Zero investigator tokens spent.
- **Outcome YES (1):** Novel person detected. Flagged for snippet investigation.

### Step 2: Focused Snippet Extraction & Parallel Dispatch (Supervisor $\to$ 4 Workers)
For suspect threads (in batches of up to 4 concurrently):
1. The Supervisor extracts windowed context snippets ($\pm 4$ turns) around candidate entities:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --thread-snippets <thread_id> --json
   ```
2. The Supervisor invokes up to 4 parallel `entity-investigator` subagents (`Model: "flash"`), passing each worker:
   - Target `thread_id` and focused candidate snippets.
   - List of known registered characters.

### Step 3: Forensic Snippet Inspection & Pragmatic Boundedness (Workers)
Each investigator subagent analyzes the window around candidate mentions:
- **Baseline Window ($4 + 1 + 4$):** Subagents start with a minimum window of 4 messages before, the target mention message, and 4 messages after ($4+1+4$).
- **Active Within-Thread Probing:** While subagents avoid reading the full thread sequentially, they can and should run targeted lexical searches (`-s "<keyword>"`) across the thread or check alternative candidate mentions (`--thread-snippets <id> --mentions "<alt>"`) if the person might be named elsewhere in the same thread.
- **Context Expansion & Direct Split Continuity:**
  - *Direct Thread Splits:* Threads are chunked (~50 messages limit). If discussion of a person starts at the immediate beginning or cuts off at the immediate end of a thread, the investigator MAY inspect the seam with the directly adjacent thread chunk (`--around <anchor_msg_id> -n 8`).
  - *Information Continuation Criterion:* Continue following turns ONLY as long as the dialogue *actively continues to discuss and provide informative details* about this specific entity.
  - *Stop Rule:* If the mention was a brief one-off or the conversation shifted topics, **STOP immediately**. Never read subsequent messages/threads once the topic has shifted, and never dig into distant past threads (e.g. 10 or 20 threads earlier).
  - *Sparse Mentions:* If evidence is insufficient to identify the person, report `status: "insufficient_data"` rather than guessing.
- **Antecedent Check:** Traces pronoun antecedents to confirm human identity (vs. drug/place/meme).
- **Relational Role:** Determines relational significance (personal/medical/professional vs. episodic bystander).
- **Subject Rebuttal Audit:** Verifies whether the subject explicitly refutes interlocutor assumptions (*"that's not my ex"*).
- **Report Return:** Submits structured findings JSON to the Supervisor. (Workers NEVER execute `--register-entity`).

### Step 4: Cross-Worker Deduplication & Atomic Registration (Supervisor)
The Supervisor receives findings from all parallel workers:
1. **Cross-Thread Deduplication:** Merges multiple references to the same person discussed across different threads into a single canonical entity.
2. **Cardinality Verification:** Distinguishes multiple individuals sharing identical kinship or role terms (e.g. `Sister_Older` vs. `Sister_Epileptic`).
3. **Atomic Registration:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role>" --desc "<Anchors & Context>"
   ```
4. **Thread Clearance:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --watchdog-check <thread_id>
   # If false alarm / bystander:
   python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "episodic_bystander"
   ```

### Step 5: Gate Clearance (Phase A Conclusion)
The Supervisor repeats the loop until the hard-stop gate passes:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate
```
Exits with code 0 (`[✓] PASSED: 100% of third-party threads are verified`).

---

### PHASE B: Deep Salient Entity Profiling & Relational Dossiers

Once the complete entity registry is established and the Watchdog Gate is resolved, the Supervisor deep-profiles all salient figures:

### Step 6: Noise Rejection & Salience Screening (No Artificial Quotas)
- **Do Not Arbitrarily Cap:** The Supervisor does NOT limit salient figures to "top 4–6". If 3, 8, or 12 figures hold enduring emotional, familial, romantic, or professional weight, **ALL of them are profiled**.
- **Omit Pure Noise / Transients:** Exclude only episodic, transactional figures (courier, mechanic from single visit, anonymous clerk).

### Step 7: Negative Boundary Injection
For each salient entity, the Supervisor formulates explicit **Negative Boundaries** (who this person is NOT and distinct traits) to prevent subagents from conflating distinct individuals (e.g. multiple suitors from the same app, multiple siblings, multiple doctors).

### Step 8: Wave-Based Parallel Profiling (1 Entity = 1 Subagent)
The Supervisor launches `entity-deep-profiler` subagents in parallel waves of up to 4 concurrent workers (`Model: "flash"`):
- **Dual Search Engine:**
  - *Lexical FTS (`-s`):* Name, alias, city, concrete milestones.
  - *Semantic Role Queries (`--semantic`):* Functional role fields (e.g. managerial workplace demands, romantic abandonment fears, parental expectations) even when proper names are omitted.
  - *Antecedent Audit (`--around <id> -n 5`):* Mandatory turn check to ensure semantic matches belong to the assigned entity.

### Step 9: Dossier Consolidation & Hand-off
The Supervisor collects structured Markdown dossiers for all salient figures, writes them to `reports/<chat_id>_entities/<Entity>.md`, and hands off the complete Cast of Characters and Relational Matrix to the Main Coordinator.

---

## 3. CLI Command Reference

```bash
# Focused candidate snippet retrieval (±4 msgs around Scaledown candidate mentions):
python3 project/scripts/query_chat.py -C <chat_id> --thread-snippets <thread_id>
python3 project/scripts/query_chat.py -C <chat_id> --thread-snippets <thread_id> --json
python3 project/scripts/query_chat.py -C <chat_id> --thread-snippets <thread_id> --mentions "<Name_or_Role>"

# Sequential scan stopping on threads with unverified entities:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan --limit 4

# Single thread verification check:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-check <thread_id>

# Check current watchdog audit progress:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-status

# Verify hard-stop gate status (exit 0 on complete, 1 on pending/detected):
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate

# Register a verified third-party entity (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role>" --desc "<Notes>"

# Skip false positive or episodic bystander thread (Supervisor ONLY):
python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "episodic_bystander"
```

---

## 4. Hard-Stop Blocking Gate & Downstream Prerequisites

The Entity Watchdog is a **strict programmatic prerequisite**:

1. **Downstream Initialization Barrier:**
   `python3 project/scripts/thread_checklist.py --init -C <chat_id>` and `python3 project/scripts/checklist.py --init -C <chat_id>` verify the watchdog gate. They immediately exit with code 1 if any third-party thread remains pending or has unregistered entities detected.
2. **Assembly Triple Hard-Stop Gate:**
   `python3 project/scripts/assemble_report.py --check-gates` verifies that all third-party threads are 100% resolved (`cleared` or `skipped`) before allowing report generation.
