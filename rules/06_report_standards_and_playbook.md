---
trigger: always_on
---

# Reporting Standards, Document Architecture & Operational Playbook

These rules govern the document architecture, formatting standards, Operational User Manual, Summary Matrix, and delivery specifications for psychological personality profiles.

> [!NOTE]
> **Scope of Application:**
> - **Comprehensive Profiling & Dossiers (Mode B):** The 4-part Thesis-First chapter structure, the 8 core dossier sections, and the Operational Playbook apply **specifically when generating comprehensive personality profiles or psychological dossiers**.
> - **Ad-Hoc Questions & Inquiries (Mode A):** When answering specific questions, checking facts, or exploring chat events, provide direct, focused answers in chat with exact verbatim citations (`[#ID | YYYY-MM-DD]`), without forcing a multi-chapter report structure.
> - **Universal Standards:** Formatting prohibitions (Section 3: No Mermaid diagrams, no ASCII art code-block timelines) and language standards (Section 4: Polish delivery by default) apply to **ALL** analytical outputs.

---

## 1. Thesis-First Analytical Architecture

Every thematic chapter in the report MUST strictly follow the 4-part Thesis-First structure:

1. `### 📌 The Core Thesis`
   - 2–3 bold, definitive sentences stating the psychological insight upfront. The reader grasps the entire finding simply by reading this thesis. No introductory filler or throat-clearing.
2. `### 🧠 In-Depth Psychological Analysis`
   - Explicit forensic mechanisms, developmental origins, ego defenses, cognitive distortions, and relational dynamics. Connect past roots to adult behavior.
3. `### 🔍 Verbatim Evidence & Case Studies`
   - Verbatim quotes from chat logs with exact message anchors and dates (`[#ID | YYYY-MM-DD]`), formatted in blockquotes (`>`).
4. `### 💡 Key Takeaway`
   - A concise, operational conclusion (1–2 punchy sentences) summarizing the practical diagnostic takeaway.

---

## 2. Mandatory Report Architecture & Components

A complete personality profile report consists of the following 8 components:

### 1. Executive Summary & Opening Motto
- **Opening Motto:** Verbatim quote encapsulating the subject's core philosophy or existential longing.
- **Case File Header:** Subject name/alias, diagnosed Attachment Style, Big Five (OCEAN) summary profile (e.g. *O: High, C: High, E: Low, A: Low-Mod, N: High*), date range analyzed, total message volume.
- **Executive Summary:** High-level psychological portrait, central conflicts, core defense architecture, and primary relational thesis.

### 2. Biographical Dossier & Life Timeline
- Origin story reconstructed chronologically across childhood, family discipline, education, relationships, and formative crucibles.
- **Timeline Formatting Standard (Chronological Bullet Flow):**
  - Format strictly as a hierarchical Markdown bullet list:
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
- **Atomic Grounding & Zero-Filler Rule:** Every descriptor, occupation, and status must be independently backed by verifiable message IDs. Unverified political or psychological labels as synthetic filler are strictly prohibited.

### 4. Core Thematic Life Spheres Chapters
- Deep dives into domains that actually emerged in the logs (Social Matrix, Work & Ambition, Worldview & Tech, Family Roots, Leisure & Animals).
- Apply the **Evidentiary Pruning Rule**: completely omit any unmentioned sphere (no placeholder disclaimers).

### 5. Attachment Style Diagnosis
- Classify primary and secondary attachment styles (Secure, Anxious-Preoccupied, Dismissive-Avoidant, Fearful-Avoidant).
- Detail specific deactivating strategies, protest behaviors, intimacy ceilings, and geographic/relational buffers.

### 6. Big Five Personality Model (OCEAN)
- Rate all 5 spectrums (Low, Moderate, High) with concrete conversational markers. Do NOT assign MBTI types.

### 7. Operational User Manual (Actionable Playbook)
A practical interaction guide comprising:
- **Blind Spots:** What the subject chronically fails to perceive about their own behavior or impact on others.
- **Emotional Triggers (Red Buttons):** Specific words, attitudes, and scenarios that spark instant defensive regression, anger, or withdrawal.
- **Unspoken Core Need:** The primary emotional hunger they yearn for but rarely voice directly.
- **Communication Protocols:** Concrete rules on how to de-escalate tension, persuade, and resolve conflict (*What NEVER to do* vs. *What ALWAYS works*).
- **Statement Reliability Index:** Where their declarations are ironclad vs. where their words represent wishful thinking, temporary venting, or phantom plans.

### 8. Concluding Summary Matrix
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

## 3. Strict Visualization & Formatting Prohibitions

1. **Strict Prohibition on Mermaid Diagrams & Flowcharts:**
   - **NEVER** generate mermaid code blocks (````mermaid```), flowcharts, sequence diagrams, or graphical node diagrams under any circumstances.
2. **Strict Prohibition on ASCII Code-Block Timelines:**
   - **NEVER** generate ASCII art pseudo-timelines or tree drawings using vertical pipes (`│`, `├──`, `└──`) inside monospace code blocks (` ``` `). They break text wrapping on mobile devices, degrade readability, and ruin document typography.
   - Format all chronologies and relational networks strictly via clean Markdown tables and structured bullet hierarchies.

---

## 4. Language Standard (Default Polish Delivery)

1. **Mandatory Default Output Language:**
   - All generated personality profile reports, intermediate modular section drafts (`reports/<subject>_sections/*.md`), dossiers, and character tables **MUST be written in Polish by default**, matching the user's analytical language and gold-standard benchmarks in `przykłądoweAnalizy/`.
2. **On-Demand Translation Only:**
   - The agent should only output profiles in English if the user explicitly requests an English version (e.g. *"produce in English"* or *"translate to English"*).
3. **Specification & Code Integrity:**
   - All rules, skills, prompt definitions, comments, and technical scripts inside `.agents/` must remain in **English**.
