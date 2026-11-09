---
trigger: always_on
---

# Reporting Standards, Architecture Invariants & Delivery Playbook

These rules govern the core analytical writing architecture, universal formatting prohibitions, output language standards, and dossier assembly requirements for psychological personality profiles.

---

## 1. Thesis-First Analytical Architecture

Every thematic chapter in the report or substantive analytical finding MUST strictly follow the 4-part Thesis-First structure:

1. `### 📌 The Core Thesis`
   - 2–3 bold, definitive sentences stating the psychological insight upfront. The reader grasps the entire finding simply by reading this thesis. No introductory filler or throat-clearing.
2. `### 🧠 In-Depth Psychological Analysis`
   - Explicit forensic mechanisms, developmental origins, ego defenses, cognitive distortions, and relational dynamics. Connect past roots to adult behavior.
3. `### 🔍 Verbatim Evidence & Case Studies`
   - Verbatim quotes from chat logs with exact message anchors and dates (`[#ID | YYYY-MM-DD]`), formatted in blockquotes (`>`).
4. `### 💡 Key Takeaway`
   - A concise, operational conclusion (1–2 punchy sentences) summarizing the practical diagnostic takeaway.

---

## 2. Universal Formatting Prohibitions & Language Standards

1. **Strict Prohibition on Mermaid Diagrams & Flowcharts:**
   - **NEVER** generate mermaid code blocks (````mermaid```), flowcharts, sequence diagrams, or graphical node diagrams under any circumstances.
2. **Strict Prohibition on ASCII Code-Block Timelines:**
   - **NEVER** generate ASCII art pseudo-timelines or tree drawings using vertical pipes (`│`, `├──`, `└──`) inside monospace code blocks (` ``` `). Format all chronologies and relational networks strictly via clean Markdown tables and structured bullet hierarchies.
3. **Mandatory Default Output Language (Polish):**
   - All generated personality profile reports, intermediate modular section drafts (`reports/<subject>_sections/*.md`), dossiers, and character tables **MUST be written in Polish by default**, matching the benchmark analyses in `przykłądoweAnalizy/`. Output in English only if explicitly requested.
4. **Specification & Code Language (English):**
   - All rules, skills, prompt definitions, comments, and technical scripts inside `project/` must remain in **English**.

---

## 3. Mandatory Dossier Assembly Skill Activation Gate

To preserve system context window capacity, the complete 8-component dossier blueprint, Markdown table schemas, and assembly pipeline are maintained in a specialized skill:

> [!IMPORTANT]
> **Activation Requirement:**
> When generating or formatting a comprehensive personality profile, biographical dossier, Cast of Characters table, Operational Playbook, or Summary Matrix, the agent **MUST activate the `dossier-report-assembly` skill**.
>
> The skill provides:
> - The complete 8-component report blueprint (Executive summary, bullet timeline, Cast of Characters, OCEAN, Attachment, Playbook, Summary Matrix).
> - Production-ready Markdown templates for tables and playbooks.
> - Modular section drafting protocol and automated compilation using `assemble_report.py`.
