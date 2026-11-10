---
trigger: always_on
---

# Life Spheres Evidentiary Standards, Checklist Gate & Investigation Protocol

These rules define the dual-layer accountability protocol, database checklist enforcement gate, and evidentiary thresholds for investigating the 6 foundational spheres of life in chat archives.

---

## 1. Dual-Layer Accountability: Database Verification vs. Report Narrative

To eliminate analytical blind spots without cluttering deliverable reports with empty negative boilerplates:

### A. Database Verification Layer (`chat.db` Checklist)
- **Mandatory Mode B Enforcement:** When conducting comprehensive personality profiling (Mode B), **100% of the 46 life sphere dimensions and sub-items must be audited and resolved in SQLite** (`life_spheres_checklist`).
- **Evidence-Backed Items (`completed`):** When queries uncover substantive behavioral evidence, mark status as `completed` with findings and anchored citations (`[#ID | YYYY-MM-DD]`).
- **Unmentioned / Insufficient Data Items (`no_data`):** If exhaustive searches yield no mentions, **the agent MUST log that the probe was attempted and mark the status as `no_data` in the database**, noting the queries executed (e.g. `notes: "Searched -s 'sport OR siłownia' --semantic 'exercise': 0 mentions found"`). No item may remain `pending`.
- **Mode A Exception:** During ad-hoc questions or targeted Q&A (Mode A), checklist initialization and tracking are **strictly disabled**.

### B. Report Narrative Layer (`reports/<subject>_personality_analysis.md`)
- **Evidence-Driven Synthesis:** Only dimensions with verifiable evidence (`completed`) are synthesized into narrative chapters following the 4-part Thesis-First structure.
- **Strict Omission of `no_data` Topics:** Dimensions verified as absent (`no_data`) are **completely omitted from the text narrative**.
- **Absolute Prohibition on Placeholder Disclaimers:** NEVER generate empty sections or negative boilerplate such as *"Brak informacji o sporcie"*, *"Temat ten nie był poruszany w rozmowie"*, or *"No information available in the archive"*.
- **Stimulus Exposure & Disinterest as an Analytical Finding:**
  - If an interlocutor introduced a topic/suggestion and the subject actively ignored it, changed the subject, or showed disinterest:
  - This is not mere absence of data; record it as a valid observation of personal boundaries or lack of engagement, avoiding forced over-pathologizing.

---

## 2. Life Spheres Database Checklist Toolchain (`checklist.py`)

All checklist state transitions and gate validations are managed via `project/scripts/checklist.py`:

```bash
# 1. Initialize 46 checklist items for the target chat:
python3 project/scripts/checklist.py --init -C <chat_id>

# 2. Check overall progress summary and sphere breakdown:
python3 project/scripts/checklist.py --status -C <chat_id>
# (Alternatively via query_chat.py):
python3 project/scripts/query_chat.py --checklist -C <chat_id>

# 3. Update an item with evidence found:
python3 project/scripts/checklist.py -C <chat_id> --update <item_id> --set-status completed \
  --notes "Identified uncompleted IT pivot [#1234 | 2021-03-04]" \
  --queries "marzenie OR rzuciłem OR startup"

# 4. Update an item after probing with no data:
python3 project/scripts/checklist.py -C <chat_id> --update <item_id> --set-status no_data \
  --notes "Queried -s 'sport OR siłownia': 0 relevant mentions found" \
  --queries "sport OR siłownia OR trening"

# 5. Batch update multiple items:
python3 project/scripts/checklist.py -C <chat_id> --batch-update <id1> <id2> --set-status <status> --notes "<notes>"

# 6. PIPELINE GATE VERIFICATION (Mandatory before report assembly):
python3 project/scripts/checklist.py --check -C <chat_id>

# 7. SAFETY WAIVER / DISABLING (For ad-hoc tasks, Q&A, or partial inquiries):
python3 project/scripts/checklist.py -C <chat_id> --waive --reason "Ad-hoc task: <description>"
# (Re-enabling when full profiling is resumed):
python3 project/scripts/checklist.py -C <chat_id> --enable
```

### Safety Waiver & Exemption Protocol:
When the agent begins a task that does **not** require comprehensive life spheres profiling (e.g. ad-hoc inquiries, verification of a single event, or focused Q&A):
- The agent can safely waive/disable the checklist using `--waive --reason "<reason>"` (or `query_chat.py --waive-checklist`).
- This marks all pending items as `not_applicable` and registers an exemption in `metadata`, ensuring `--check` returns exit code 0 (`PASSED (EXEMPT)`).
- When comprehensive personality profiling (Mode B) is explicitly requested later, running `--enable` or `--init --reset` cleanly re-engages the full 46-item audit.

### The Hard Stop Blocking Gate (100% Resolution Invariant):
Before proceeding to Step B.5 (Dossier Assembly) or drafting final profile chapters, the agent MUST run:
```bash
python3 project/scripts/checklist.py --check -C <chat_id>
```
- If the script exits with `code 0`: All items are accounted for (`completed`, `no_data`, or `not_applicable`). Proceed to Step B.5.
- If the script exits with `code 1`: **STOP.** Review the listed `pending` items, probe each with targeted queries via `query_chat.py`, and resolve their statuses.

---

## 3. Mandatory Life Spheres Skill Activation Gate

To preserve system context, detailed forensic diagnostic questions, concrete behavioral probing criteria across all life spheres, and bilingual search lexicons are maintained in specialized skills:

> [!IMPORTANT]
> **Activation Requirement:**
> When conducting Phase 4 of an investigation (auditing lifestyle habits, work ethic, unfulfilled ambitions, friendships, spending psychology, domestic order, hobbies, or technology stance), the agent **MUST activate the `life-spheres-investigation` skill**.
>
> The skill provides:
> - Concrete forensic probing criteria across all 6 core life spheres.
> - Detailed operational checklists and behavioral probing questions.
> - The Master Bilingual Probing Lexicon (Polish FTS5 keywords and English semantic vector queries).
> - Concrete CLI recipes for `query_chat.py` and step-by-step verification procedures.
