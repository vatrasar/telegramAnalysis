---
name: entity-watchdog-audit
description: >-
  Sequential System-1 cursor and double-check loop for identifying overlooked third-party entities
  in multi-party chat threads. Use during entity verification or watchdog scans.
---

# Sequential System-1 Entity Watchdog & Verification Loop

This skill provides the operational protocol, System-1 gatekeeper checks, and CLI toolchain for identifying third-party entities across multi-party conversation threads without context flooding.

---

## 1. Overview & Single-Entity Blindness Defense

In longitudinal group or multi-party chat archives, participants frequently discuss multiple external entities (friends, suitors, coworkers, family). Agents often suffer from **Single-Entity Blindness**—identifying the first prominent character in a thread and stopping, prematurely overlooking secondary figures.

The **Sequential Watchdog Loop** counters this by using a lightweight System-1 decision call as a gatekeeper on each thread ($T_1 \to T_2 \dots \to T_N$) before escalating novel entities to the agent (System-2) for extraction.

---

## 2. The 4-Step Watchdog Protocol

### Step 1: System-1 Gatekeeper Check
For each thread flagged with `mentions_third_party = 1`:
- System-1 evaluates the transcript against the set of currently registered entities $S$:
  *"Given known entities [S], does this dialogue mention ANY other third party, acquaintance, family member, or suitor?"*
- **Outcome NO (0):** Thread contains only known entities. It is marked `cleared` and skipped automatically. Zero agent context tokens spent.
- **Outcome YES (1):** Novel or unrecognized entity detected. The cursor halts on thread $T_i$ and presents it to the agent.

### Step 2: Agent Extraction & Registration (System-2)
The agent reads thread $T_i$, determines the character's name/descriptor, role, and relationship, and registers the entity:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role>" --desc "<Descriptor>"
```
The entity registry updates: $S \gets S \cup \{\text{Name}\}$.

### Step 3: Adversarial Double-Check on Same Thread
The agent **does not immediately advance** to the next thread. Instead, re-query the same thread $T_i$ against the updated set $S$:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-check <thread_id>
```
- **If NO (0):** All entities in $T_i$ are accounted for. The thread is marked `cleared`, and the scanner proceeds to $T_{i+1}$.
- **If YES (1):** Another overlooked entity remains in $T_i$. Repeat extraction.

### Step 4: False Positive Breakout Guard
If after manual inspection the agent confirms that no additional human entity exists (e.g., System-1 mistook medication, place, or slang for a proper name), skip the thread to release the cursor:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "false_positive_bystander"
```

---

## 3. CLI Command Reference

```bash
# Sequential scan stopping on threads with unverified entities:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan --limit 10

# Single thread verification check:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-check <thread_id>

# Check current watchdog audit progress:
python3 project/scripts/query_chat.py -C <chat_id> --watchdog-status

# Verify hard-stop gate status (exit 0 on complete, 1 on pending/detected):
python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate

# Register a verified third-party entity:
python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role>" --desc "<Notes>"

# Skip false positive thread:
python3 project/scripts/query_chat.py -C <chat_id> --skip-thread <thread_id> --reason "false_positive"
```

---

## 4. Hard-Stop Blocking Gate & Downstream Prerequisites

The Entity Watchdog is not an optional suggestion; it is a **programmatic prerequisite**:

1. **Downstream Initialization Barrier:**
   `python3 project/scripts/thread_checklist.py --init -C <chat_id>` and `python3 project/scripts/checklist.py --init -C <chat_id>` verify the watchdog gate. They immediately exit with code 1 if any third-party thread remains pending or has unregistered entities detected.
2. **Assembly Triple Hard-Stop Gate:**
   `python3 project/scripts/assemble_report.py --check-gates` verifies that all third-party threads are 100% resolved (`cleared` or `skipped`) before allowing report generation. If watchdog threads remain pending, assembly aborts with exit code 1.
