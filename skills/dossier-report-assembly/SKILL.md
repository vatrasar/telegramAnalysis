---
name: dossier-report-assembly
description: >-
  Blueprint, section templates, and assembly tools (assemble_report.py) for final psychological personality
  profiles. Use when drafting or compiling final dossiers.
---

# Dossier Report Blueprint & Assembly Skill

This skill defines the complete document architecture, chapter templates, markdown schemas, and modular assembly workflow for producing comprehensive psychological personality dossiers from chat archives.

---

## 1. Overview

A full personality profile is an extensive, multi-chapter document. To prevent context window exhaustion during generation and ensure structural consistency:
1. Profiles are drafted modularly into section files (`reports/<subject>_sections/`).
2. Final compilation is automated via `assemble_report.py`.
3. Standardized Markdown schemas are applied for relational constellations, playbooks, and summary matrices.

---

## 2. When to Use

Activate this skill whenever:
- Structuring and drafting a comprehensive personality profile or psychological dossier (Mode B).
- Formatting the **Cast of Characters** relational constellation table.
- Formulating the **Operational User Manual** (Actionable Playbook).
- Compiling the final **Summary Matrix**.
- Assembling modular section files into a single deliverable via `assemble_report.py`.

---

## 3. The 8 Core Dossier Components

A complete personality dossier report consists of these 8 sequential components:

### 1. Executive Summary & Opening Motto
- **Opening Motto:** Verbatim quote encapsulating the subject's core philosophy or existential longing.
- **Case File Header:** Subject name/alias, diagnosed Attachment Style, Big Five (OCEAN) summary profile (e.g. *O: High, C: High, E: Low, A: Low-Mod, N: High*), date range analyzed, total message volume.
- **Executive Summary:** High-level psychological portrait, central conflicts, core defense architecture, and primary relational thesis.

### 2. Biographical Dossier & Life Timeline
- Origin story reconstructed chronologically across childhood, family discipline, education, relationships, and formative crucibles.
- **Timeline Formatting Standard (Chronological Bullet Flow):**
  Format strictly as a hierarchical Markdown bullet list (never ASCII or Mermaid):
  ```markdown
  ### 📅 Chronological Life Timeline
  * **[Year / Date Span] — [Phase or Formative Theme Title]**
    * **[Specific Event / Crucible]:** Detailed narrative, psychological impact, and verbatim anchor `[#ID | YYYY-MM-DD]`.
    * **[Additional Dynamic]:** Context and observations.
  ```

### 3. Cast of Characters (Relational Constellation)
- Mandatory 3-column Markdown table:
  ```markdown
  | Postać / Rola | Identyfikacja i Status | Główne Motywy i Dynamika Relacyjna |
  | :--- | :--- | :--- |
  | **[Postać / Rola]** | [Zweryfikowane fakty, status, kontekst] | [Powracające motywy, dynamika, punkty tarć] |
  ```
- **Atomic Grounding & Zero-Filler Rule:** Every descriptor, occupation, and status must be backed by verifiable message IDs. Unverified political or psychological labels as synthetic filler are strictly prohibited.

### 4. Core Thematic Life Spheres Chapters
- Deep dives into domains that actually emerged in the logs (Social Matrix, Work & Ambition, Worldview & Tech, Family Roots, Leisure & Animals).
- Follow the 4-part Thesis-First chapter structure:
  1. `### 📌 The Core Thesis` (2–3 bold definitive sentences)
  2. `### 🧠 In-Depth Psychological Analysis` (Mechanisms, ego defenses, developmental roots)
  3. `### 🔍 Verbatim Evidence & Case Studies` (Anchored quotes `[#ID | YYYY-MM-DD]`)
  4. `### 💡 Key Takeaway` (1–2 punchy practical sentences)
- Apply the **Evidentiary Pruning Rule**: completely omit any unmentioned sphere (no placeholder disclaimers).

### 5. Attachment Style Diagnosis
- Classify primary and secondary attachment styles (Secure, Anxious-Preoccupied, Dismissive-Avoidant, Fearful-Avoidant).
- Detail specific deactivating strategies, protest behaviors, intimacy ceilings, and geographic/relational buffers.

### 6. Big Five Personality Model (OCEAN)
- Rate all 5 spectrums (Low, Moderate, High) with concrete conversational markers. Do NOT assign MBTI types.

### 7. Tactical Communication & De-escalation Playbook
A practical, prescriptive interaction manual:
- **Emotional Triggers (Red Buttons):** Specific words, attitudes, and scenarios that spark instant defensive regression, anger, or withdrawal.
- **Early Warning Indicators:** Subtle shifts in communication frequency or tone preceding escalation.
- **Acute Phase Step-by-Step Procedure:** Concrete rules on how to de-escalate tension (mandatory cooldown windows, emotional validation phrasing, verbal minimalism).
- **Categorical Do's and Don'ts:** Explicit best practices vs forbidden behaviors, grounded in real chat case studies.
- **Boundary Enforcement:** Constructive confrontation formulas setting interpersonal limits without triggering abandonment panic.

### 8. Personal Creed, Social Norms & Quirks Matrix
A dedicated profile grounding the subject's everyday life rules, societal views, and visceral tastes:
- **Relational & Dating Rules:** Norms on dating etiquette, who pays, gender expectations, lending money to friends, honesty vs. diplomacy.
- **Socio-Economic Philosophy:** Concrete institutional/economic convictions (universal pensions vs capital systems, tax burden, state role).
- **Lifestyle Quirks & Comfort Standards:** Distinct consumption habits, comfort/fashion standards (e.g. aversion to formal wear/jeans).
- **Culinary Preferences & Pet Peeves:** Staple everyday foods, preferred cuisines, and visceral daily irritants (*pet peeves*).

### 9. Statement Reliability Index & Defenses
- **Statement Reliability Index:** Where their declarations are ironclad vs. where their words represent wishful thinking, temporary venting, or phantom plans.
- **Cognitive Blind Spots:** What the subject chronically fails to perceive about their own behavior or impact on others.
- **Unspoken Core Need:** The primary emotional hunger they yearn for but rarely voice directly.
- **Defusing Cognitive Distortions & Manipulation:** Concrete response templates neutralizing blame-shifting, minimization, and double binds.

### 10. Concluding Summary Matrix
A structured markdown synthesis table:

```markdown
## Summary Matrix

| Wymiar Psychologiczny | Obserwowane Zachowanie | Źródło Rozwojowe i Ukryty Sens |
| :--- | :--- | :--- |
| **Big Five (OCEAN)** | [np. O: High, C: High, E: Low, A: Low-Mod, N: High] | [np. Intelektualizacja i perfekcjonizm jako zbroja przed chaosem emocjonalnym] |
| **Styl Przywiązania** | [np. Lękowo-Unikający (Pancerz deaktywacyjny do momentu silnej więzi)] | [np. Obserwacja uwięzionego małżeństwa matki; wczesna parentyfikacja] |
| **Postawa Społeczna** | [np. Wąski krąg zaufanych; bezwzględny door-slamming przy nielojalności] | [np. Ochrona przed zdradą; unikanie odsłonięcia przed przypadkowymi kontaktami] |
| **Odpowiedzialność** | [np. Warunkowe przeprosiny ("Przepraszam JEŚLI"); intelektualizacja] | [np. Perfekcjonistyczne superego, w którym błąd wywołuje paraliżujący wstyd] |
| **Niezaspokojona Potrzeba**| [np. Pragnienie bezwarunkowej akceptacji bez konieczności udowadniania wartości] | [np. Dziecięca aprobata uzależniona wyłącznie od wybitnych osiągnięć] |
```

---

## 4. Modular Section Drafting & Supervisory Assembly Workflow

To prevent context exhaustion and ensure strict quality control during deep profiling, the drafting and compilation phase (Step B.6) is orchestrated by the **Dossier Assembly Supervisor** (`dossier-supervisor`) after the Main Coordinator clears Step B.5 (Triple Hard-Stop Gate verification & custom section approval):

### Step 1: Section Roadmap Initialization
The `dossier-supervisor` receives the target `chat_id`, subject identifier, and approved custom sections from the Main Coordinator, auditing existing modular sections (e.g. Life Spheres `05_*` from Step B.3) to establish the roadmap:
```
reports/<subject>_sections/
├── 01_dossier.md                 # Executive summary & biographical timeline
├── 02_cast.md                    # Cast of characters relational constellation table
├── 03_thematic_spheres.md        # Core life spheres (social, work, worldview, family, leisure)
├── 03_custom_<slug>.md           # Approved custom sections passed by Main Coordinator
├── 04_attachment_ocean.md        # Attachment style diagnosis & Big Five ratings
├── 05_tactical_playbook.md       # Tactical Communication & De-escalation Playbook (Ch. 7)
├── 06_creed_and_quirks.md        # Personal Creed, Norms & Quirks Matrix (Ch. 8)
├── 07_reliability_and_defenses.md# Statement Reliability Index & Defenses (Ch. 9)
└── 08_matrix.md                  # Concluding Summary Matrix (Ch. 10)
```

### Step 2: Parallel Chapter Drafting & Subsection Stitching
The `dossier-supervisor` dispatches specialized worker subagents in parallel (`Model: "flash"`):
- `chapter-drafter`: Operates as the **Chapter Supervisor** for all assigned narrative, clinical, tactical, and custom chapters.
  - Deconstruct each chapter into 4–6 modular subsections staged under `reports/<subject>_sections/<chapter_name>_subsections/`.
  - Dispatch `subsection-drafter` for each subpoint.
  - Enforce the **20-fact threshold** via `cluster_facts.py` (partitioning facts into semantic clusters when facts > 20).
  - Integrate and audit subsections using `stitch_chapter.py`:
    ```bash
    python3 project/scripts/stitch_chapter.py \
      -d reports/<subject>_sections/<chapter_name>_subsections/ \
      -o reports/<subject>_sections/<chapter_filename>.md \
      --chapter-title "<Title>"
    ```

### Step 3: Synthesis, QA & Gate-Checked Assembly
1. The supervisor synthesizes the Concluding Summary Matrix (`08_matrix.md`) and audits all drafts for code fence closure, anchored citations, and absence of Mermaid/ASCII trees.
2. Execute the automated assembly script:
```bash
python3 project/scripts/assemble_report.py \
  --sections-dir reports/<subject>_sections/ \
  -o reports/<subject>_personality_analysis.md \
  --check-gates
```
- The script automatically verifies all 3 investigative gates as a programmatic safety net.
- Verifies code fence closure.
- Automatically generates the Table of Contents.
- Validates structural completeness.

---

## 5. Verification Checklist

Before finalizing the dossier report, verify:
- [ ] Did all three investigative gates pass with exit code 0?
  - Entity Watchdog: `python3 project/scripts/query_chat.py -C <chat_id> --check-watchdog-gate`
  - Thread Forensic Checklist: `python3 project/scripts/thread_checklist.py --check -C <chat_id>`
  - Life Spheres Checklist: `python3 project/scripts/checklist.py --check -C <chat_id>`
- [ ] Are all 10 mandatory components present?
- [ ] Is the document written in Polish by default?
- [ ] Are all thematic chapters structured with the 4-part Thesis-First headings?
- [ ] Is the timeline formatted strictly as Markdown bullets (no Mermaid, no ASCII trees)?
- [ ] Does the Cast of Characters table include exact anchored citations `[#ID | YYYY-MM-DD]`?
- [ ] Are all unmentioned life spheres omitted without placeholder text?
- [ ] Has `assemble_report.py` finished cleanly with exit code 0?
