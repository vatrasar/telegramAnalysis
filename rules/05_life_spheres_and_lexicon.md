---
trigger: always_on
---

# Life Spheres Evidentiary Standards & Checklist Gate

These rules define the dual-layer accountability protocol, semantic vector search mandates, and evidentiary thresholds for investigating the 6 foundational life spheres in chat archives.

---

## 1. Dual-Layer Accountability: Database Verification vs. Report Narrative

To eliminate analytical blind spots without cluttering deliverable reports with empty negative boilerplates:

### A. Database Verification Layer (`chat.db` Checklist)
- **Mandatory Mode B Enforcement:** In comprehensive personality profiling (Mode B), **100% of the 46 life sphere dimensions must be audited and resolved in SQLite** (`life_spheres_checklist`).
- **Evidence-Backed Items (`completed`):** When queries uncover substantive evidence, mark as `completed` with findings and anchored citations (`[#ID | YYYY-MM-DD]`). Core attitudinal and psychological dimensions (Spheres B, C, E, key items in A, D) MUST record semantic vector search queries (`--semantic-queries`).
- **Unmentioned / Insufficient Data Items (`no_data`):** If exhaustive searches yield no mentions, log that the probe was attempted and mark as `no_data`, explicitly logging both lexical terms (`--queries`) and semantic vector queries (`--semantic-queries`). No item may remain `pending`.
- **Mode A Exemption:** In ad-hoc Q&A (Mode A), checklist enforcement is strictly disabled (or waived via `--waive-checklist`).

### B. The Epistemic Primacy of Semantic Vector Search
1. **The Inadequacy of Lexical Keywords for Human Attitudes:**
   Informal chat interlocutors never use clinical, academic, or ideological labels.
   - Searching `-s "polityka"` misses actual discussions on inflation, municipal taxes, election candidates, and border regulations.
   - Searching `-s "oszczędzanie"` misses everyday financial habits, second-hand buying on OLX, spending guilt, and debt aversion.
   - Searching `-s "lęk przed bliskością"` misses humor deflections, deactivating maneuvers, and subject-changing.
   Therefore, dense semantic vector search (`query_chat.py --semantic "<concept>"`) is the **primary discovery tool**.
2. **Absolute Ban on Keyword-Only `no_data` Claims:**
   Marking any life sphere as `no_data` based solely on a failed lexical search (`-s`) is strictly classified as an **Epistemic Invariant Violation (False Negative Hallucination)**. To mark an item `no_data`, the agent MUST execute at least one semantic vector search query (`--semantic`) and record it in `life_spheres_checklist` via `--semantic-queries`.

### C. Report Narrative Layer
- **Evidence-Driven Synthesis:** Only dimensions with verifiable evidence (`completed`) are synthesized into narrative chapters.
- **Strict Omission of `no_data` Topics:** Dimensions verified as absent (`no_data`) are **completely omitted from the text narrative**.
- **Absolute Ban on Placeholder Disclaimers:** NEVER generate empty sections or negative boilerplate such as *"Brak informacji o sporcie"*, *"Temat ten nie był poruszany"*, or *"No information available"*.
- **Exposed Stimulus with Disinterest:** If an interlocutor introduced a topic and the subject actively ignored or evaded it, record this as a valid observation of personal boundaries or lack of engagement.

---

## 2. Hard-Stop Blocking Gate (100% Resolution & Semantic Verification Invariant)

Before moving to Step B.5 (Dossier Assembly) or drafting profile chapters, the agent MUST run:
```bash
python3 project/scripts/checklist.py --check -C <chat_id>
```
- **Exit Code 0:** All 46 items are resolved (`completed`, `no_data`, or `not_applicable`) AND all mandatory semantic vector search requirements are satisfied. Proceed with assembly.
- **Exit Code 1:** Stop immediately. Fix remaining pending items or missing semantic vector probes and re-verify.

---

## 3. Investigation Skill Activation Gate

For forensic diagnostic questions, probing criteria across the 6 life spheres, bilingual Polish/English search lexicons, semantic vector query recipes, and detailed `checklist.py` management commands, activate the `life-spheres-investigation` skill.
