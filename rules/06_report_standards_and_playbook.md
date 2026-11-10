---
trigger: always_on
---

# Reporting Standards, Architecture Invariants & Delivery Playbook

These rules govern the core analytical writing architecture, formatting prohibitions, and output language standards for psychological personality profiles.

---

## 1. Thesis-First Analytical Architecture

Every thematic chapter or substantive analytical finding MUST follow the 4-part Thesis-First structure:

1. `### 📌 The Core Thesis`
   - 2–3 bold, definitive sentences stating the psychological insight upfront.
2. `### 🧠 In-Depth Psychological Analysis`
   - Forensic mechanisms, developmental roots, ego defenses, cognitive distortions, and relational dynamics.
3. `### 🔍 Verbatim Evidence & Case Studies`
   - Direct quotes with exact message anchors and dates (`[#ID | YYYY-MM-DD]`), formatted in blockquotes (`>`).
4. `### 💡 Key Takeaway`
   - 1–2 punchy sentences summarizing the practical diagnostic conclusion.

---

## 2. Formatting Prohibitions & Language Standards

1. **Strict Ban on Mermaid Diagrams:** NEVER generate mermaid code blocks (````mermaid```), flowcharts, sequence diagrams, or graphical node diagrams.
2. **Strict Ban on ASCII Code-Block Timelines:** NEVER generate ASCII art pseudo-timelines or tree drawings using vertical pipes (`│`, `├──`, `└──`) inside monospace code blocks. Format chronologies and networks strictly via clean Markdown tables and bullet hierarchies.
3. **Mandatory Default Output Language (Polish):** All generated personality profile reports, intermediate modular section drafts (`reports/<subject>_sections/*.md`), dossiers, and character tables MUST be written in Polish by default. Output in English only if explicitly requested.
4. **Specification & Code Language (English):** All rules, skills, prompts, comments, and scripts inside `project/` must remain in English.

---

## 3. Dossier Assembly Skill Gate

For the full 8-component report blueprint, Cast of Characters schema, Operational Playbook templates, Summary Matrix, and automated compilation via `assemble_report.py`, activate the `dossier-report-assembly` skill.
