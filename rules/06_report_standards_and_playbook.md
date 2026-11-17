---
trigger: always_on
---

# Delivery Standards, Formatting Invariants & Language Policy

These rules govern the presentation standards, formatting prohibitions, and output language policy for deliverables and coordinator communications.

---

## 1. Formatting Prohibitions & Structural Standards

1. **Strict Ban on Mermaid Diagrams:** NEVER generate mermaid code blocks (````mermaid```), flowcharts, sequence diagrams, or graphical node diagrams.
2. **Strict Ban on ASCII Pseudo-Timelines:** NEVER generate ASCII art pseudo-timelines or tree drawings using vertical pipes (`│`, `├──`, `└──`) inside monospace code blocks. Format chronologies and relationship maps strictly via clean Markdown tables or standard bullet hierarchies.
3. **No Synthetic Placeholder Disclaimers:** NEVER write negative boilerplates such as *"Brak danych"*, *"No information available"*, or *"Temat ten nie był poruszany"*. Omit unevidenced topics entirely.

---

## 2. Language Standards

1. **Mandatory Default Output Language (Polish):** All conversation summaries, intermediate artifacts (such as `reports/<chat_id>_facts_snapshot.md`), and final deliverables MUST be written in analytical Polish by default. Output in English only if explicitly requested by the user.
2. **Specification & Code Standard (English):** All system prompts, agent definitions, rules, skills, code, and technical comments inside `project/` must remain in English.

---

## 3. Dossier Assembly Supervisory Delegation (Step B.6)

- Final report drafting and assembly are strictly delegated to the **Dossier Assembly Supervisor** (`dossier-supervisor`).
- For the full report blueprint, playbook templates, summary matrix, and automated compilation via `assemble_report.py`, activate the `dossier-report-assembly` skill.
