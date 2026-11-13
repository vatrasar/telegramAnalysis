---
trigger: always_on
---

# Life Spheres Evidentiary Standards & Checklist Gate

These rules define the dual-layer accountability protocol, semantic vector search mandates, and evidentiary thresholds for investigating the 6 foundational life spheres in chat archives.

---

## 1. Dual-Layer Accountability: Database Verification vs. Report Narrative

### A. Database Verification Layer (`chat.db` Checklist)
- **Mandatory Mode B Enforcement:** In comprehensive profiling (Mode B), **100% of the 46 life sphere dimensions must be audited and resolved in SQLite** (`life_spheres_checklist`).
- **Pre-Extracted Evidence Check (Anti-Redundancy):** Before issuing raw queries across the database, the investigator MUST check `query_chat.py -C <chat_id> --facts-for-sphere <sphere>` and `--inspected-threads` to absorb pre-extracted quotes from earlier pipeline phases and avoid re-reading previously audited threads.
- **Evidence-Backed Items (`completed`):** Log findings and quote anchors (`[#ID | YYYY-MM-DD]`). Core attitudinal and psychological dimensions (Spheres B, C, E, key items in A, D) MUST record semantic vector search queries (`--semantic-queries`).
- **Absolute Ban on Keyword-Only `no_data`:** To mark an item as `no_data`, the agent MUST execute and log at least one semantic vector query (`--semantic-queries`). Concluding absence based solely on lexical keyword search is an **Epistemic Invariant Violation**.
- **Mode A Exemption:** In ad-hoc Q&A (Mode A), checklist is waived via `--waive-checklist`.

### B. Report Narrative Layer
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
- **Exit Code 1:** Stop immediately. Probe remaining pending items or missing semantic vector queries and re-verify.

---

## 3. Investigation Skill Activation Gate

For forensic diagnostic questions, probing criteria across the 6 life spheres, bilingual Polish/English search lexicons, semantic vector query recipes, and detailed `checklist.py` management commands, activate the `life-spheres-investigation` skill.
