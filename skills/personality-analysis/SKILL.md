---
name: personality-analysis
description: >-
  Conducts deep, thesis-driven psychological and personality profiling from longitudinal chat logs
  and transcripts. Uses an investigative detective/profiler mindset to reconstruct biographical
  dossiers, diagnose behavioral MBTI and attachment styles, audit all intensive discussions, map
  the cast of characters, analyze life spheres (friends, work, worldview), detect internal contradictions
  and unconscious blind spots, and generate actionable operational manuals. Formatted in a modular
  Thesis-First architecture.
---

# Personality Profiling & Behavioral Intelligence Skill

This skill defines the methodology, investigative mindset, and modular document architecture for generating forensic-grade psychological portraits from longitudinal chat archives (often spanning tens of thousands of messages across multiple years).

It transforms raw message logs into an exhaustive psychological dossier that deciphers **who the person actually is**, traces their **formative roots**, exposes their **unconscious defense mechanisms**, classifies their **Behavioral MBTI** and **Attachment Style**, maps their **Relational Constellation**, and compiles an **Actionable Operational User Manual** for interacting with them.

---

## 1. The Investigative Detective Mindset

Rather than operating as a passive summarizer or a checklist-bound automaton, the agent adopts the posture of an **Inquisitive Psychological Profiler / Detective**:

1. **Active Hypothesis Formation & Testing:**
   - Detect anomalies, unusual silences, emotional shifts, or sudden outbursts, formulate behavioral leads, and cross-examine them across the entire dataset.
   - **Cross-Examination (Words vs. Actions):** Never accept self-descriptions at face value. If the subject claims *"I never hold grudges"*, actively test this declaration against recorded behavior during conflicts. Expose the fractures between the conscious persona and recorded reality.
2. **"Connecting the Dots" (The Profiler's Board):**
   - Synthesize disparate fragments: Connect a childhood discipline memory $\to$ to a career choice $\to$ to an ideological debate stance $\to$ to an adult relational defense.
3. **Heuristic Flexibility (Anti-Token Burning):**
   - Do not waste API tokens investigating every trivial silence or small-talk greeting. Focus analytical attention where emotional stakes, cognitive density, or behavioral friction are highest.

---

## 2. Multi-Stage Investigative Workflow

> [!IMPORTANT]
> **Mandatory Ingestion & Indexing Prerequisite:**
> Before initiating Phase 1 or Phase 2, the agent must ensure that:
> 1. Pre-flight verification (`project/scripts/setup_config.py`) succeeded with Exit Code 0.
> 2. Analytical database was built cleanly without cross-subject contamination (`project/scripts/db_builder.py <file> -o chat.db --clean` or via a dedicated subject database `-o chat_<subject>.db`).
> 3. Semantic vector embeddings were generated (`project/scripts/vector_indexer.py --db chat.db --index`).
> Deep psychological exploration and semantic search (`--semantic`) strictly depend on indexed vector embeddings; never skip indexing or silently downgrade to keyword matching.

```
[Phase 1: Macro-Recon & Anomalies] 
   └── --stats, --timeline, --gaps, --burning-days, --intensive-threads
[Phase 2: Biographical Dossier & Cast of Characters]
   └── Chronological Timeline + Relational Constellation Mapping
[Phase 3: All Intensive Discussions & Ideology]
   └── 3-Point Thread Inspection (Trigger → Core Debate → Resolution)
[Phase 4: Full Spectrum Life Spheres & Forensic Dimensions]
   └── Spheres A–F + Behavioral MBTI + 11 Forensic Psychological Layers
[Phase 5: Modular Drafting & Automated Assembly]
   └── Draft sections in modular files → Assemble with assemble_report.py
```

---

### Phase 1: Macro-Reconnaissance & Anomaly Detection

Before reading raw text or forming early impressions, establish the quantitative landscape using `project/scripts/query_chat.py`:

1. **Macro Balance (`--stats`):** Total message volume, date ranges, word-share percentages, and average words per message.
2. **Activity Chronology (`--timeline`):** Monthly ebb and flow; locate multi-month peaks of intensity or prolonged dormant phases.
3. **Silence & Reconnection Ratios (`--gaps --min-hours 24`):**
   - Who breaks silences $>24$h, $>5$ days, or $>14$ days?
   - Identify who actively sustains the relationship vs. who withdraws.
4. **Burning Days (`--burning-days`):**
   - Identify statistically anomalous days ($\mu + 2\sigma$ message/word volume). These pinpoint emotional crises, late-night confrontations, breakthrough disclosures, or intense intellectual battles.
5. **Substantive Dialogue Threads (`--intensive-threads`):**
   - Filter out small talk and isolate high-volume discussions ranked by total substantive words and interaction density.

---

### Phase 2: Biographical Dossier & Cast of Characters

#### 1. Biographical Dossier Reconstruction (Origin Story)
People rarely narrate their life sequentially; they drop autobiographical crumbs across years of conversation. The profiler collects these fragments to reconstruct a chronological **Life Timeline**:
- **Baseline Identity:** Age, education, current profession, living situation, socioeconomic background.
- **Formative Chapters:** Childhood, family atmosphere, parental discipline, sibling dynamics, school/university years, pivotal relocations.
- **Relational History:** Significant past romantic relationships, breakups, betrayals, formative lessons.
- **Turning Points (Crucibles):** Severe illness, bereavement, financial crisis, career shifts, therapy, or moments of profound loss of control.

> [!CAUTION]
> **Biographical Integrity & Entity Resolution Engine**
> 1. **Proportional Verification (The Materiality Principle):**
>    - *The Golden Test:* *"Does attributing this action/event to Person B instead of Person A alter the meaning, gravity, or analytical takeaway?"*
>    - *Low-Stakes (0 tokens wasted):* Casual activities, moods, media consumption (*"watching a movie with indian guy"*, *"bored with friend"*). If the exact identity does not alter the psychological conclusion about the subject, DO NOT launch identity searches. Treat as generic "friend/partner" without burning tokens.
>    - *High-Stakes (Mandatory Verification Gate):* Trigger targeted identity verification whenever attributing any **consequential or high-gravity event**, including:
>      a) Writing start/end dates or relationship durations in the biographical timeline (**The Span Claim Gate**).
>      b) Consequential or extreme events: crimes, violence, major financial exchanges, severe betrayal, or legal/physical conflicts.
>      c) Character & relational pathology attributions: assigning persistent manipulation, harassment, or toxic dynamics to a specific person.
>      d) Core psychological crucibles: formative traumas, foundational trust fractures, and primary attachment wounds.
> 2. **Relational Roles vs. Demographic Attributes (The NPC Filter):**
>    - Relational roles (*"sister"*, *"ex"*, *"boss"*, *"therapist"*) denote guaranteed bonds with the subject (distinguishing them from strangers/NPCs).
>    - **Bond $\neq$ Uniqueness:** A relational role guarantees a bond, but does **NOT** guarantee a 1-to-1 individual mapping (a subject can have multiple sisters simultaneously, or sequential bosses and partners across different years).
>    - Demographic attributes (*"indian guy"*, *"policeman"*, *"blonde girl"*) are surface descriptors. Never promote an episodic demographic encounter (e.g. stranger at a mall, brief chatroom encounter) into the Cast of Characters. Categorize as **Episodic Bystander / NPC**.
> 3. **Action/Behavioral Signature & Conversational Inertia:**
>    - In active relational eras (e.g. 2023–2024 breakup aftermath), generic references (*"indian guy"*, *"that guy"*) sharing a romantic/partner behavioral signature (jealousy, commitment battles, marriage demands, breakup grief) inherit the dominant partner (Hilal) via Conversational Inertia at **O(1) zero token overhead**.
>    - An interaction lacking a romantic signature (e.g. passive listener on a chat in 2020) does not strictly exclude the partner, but represents **Lack of Evidentiary Proof**—it must never be used to anchor a romantic relationship span without explicit identity confirmation.
> 4. **Cardinality State Machine ($K=1$ vs. $K \ge 2$) & Role Containers:**
>    - *Uniqueness Assumption ($K=1$):* If only one person is known in a relational role across the entire archive (e.g. subject explicitly has only one sister), map directly to that person. Do not create artificial unresolved overhead.
>    - *Concurrent Multi-Entity Collision ($K \ge 2$, e.g. Multiple Sisters / Multiple Peters):* If multiple individuals hold the same role simultaneously (e.g. one sister married in London, another aged 12), a bare mention (*"my sister"*) CANNOT be mapped to an individual without a distinguishing anchor (name, age, city, topic continuity). Route to a collective role container (e.g. `Sister_Unresolved`).
>    - *Sequential Roles Across Timelines (e.g. Bosses, Therapists, Partners):* A role like *"my boss"* changes over time across career pivots. It maps to a specific person ONLY when grounded in the chronological employment timeline (e.g. Boss at Company A in 2021 vs. Boss at Company B in 2023). If the employer context is ambiguous, route to `Boss_Unresolved`.
>    - *Container-Level Psychological Analysis:* In psychological analyses of family dynamics or authority relations, analyze the interaction at the container level without forcing a premature or false biographical attribution.
> 5. **Negative Anchor Audit & Span Claim Gate:**
>    - Query for definitive negative milestones (e.g. `boyfriend OR chłopak OR ex OR first time OR never OR until`). An explicit quote such as *"I didn't even have a boyfriend until last year"* is an iron-clad falsification gate that instantly disqualifies earlier romantic relationships.
>    - Never synthesize continuous multi-year spans (e.g. "2020–2023") by interpolating between disconnected mentions. Fact-pin every timeline claim with supporting message IDs (`[#ID | YYYY-MM-DD]`).

#### 2. Cast of Characters (Relational Constellation)
Systematically audit all significant recurring third parties mentioned in the logs:
- **Family Members:** Parents, siblings, grandparents, children, in-laws.
- **Friends & Acquaintances:** Close confidants vs. superficial social contacts (identified by name/nickname).
- **Romantic Partners:** Current partner, ex-partners, romantic prospects.
- **Professional Figures:** Bosses, mentors, coworkers, clients.
- **Rivals / Adversaries:** Individuals with whom the subject entered sharp dispute or estrangement.

For each figure, determine:
- **Exact Identification:** Distinct name/alias, active dates, and context of meeting. If multiple figures share a nationality or generic label, list them as explicitly separate entities.
- **Their Role:** Authority figure, emotional anchor, dependent responsibility, rival, or trigger.
- **Recurring Themes:** What situations invoke this person?
- **Emotional Stance & Boundaries:** Does the subject show deference, resentment, warmth, contempt, envy, or filial guilt? Can they set firm boundaries, or do they capitulate?

---

### Phase 3: All Intensive Discussions & Ideology

Examine **every intensive discussion** identified in Phase 1 (no arbitrary cutoff limits). 

#### The 3-Point Thread Inspection Method
Inspect substantive dialogue threads efficiently without getting bogged down in repetitive lines:
1. **The Trigger (Start):** What initiated the exchange? (A news article, personal slight, philosophical question, unsolicited advice?).
2. **The Core Stances (Peak):** Inspect the longest, heaviest messages where the subject defends their position, articulates values, or reacts under pressure.
3. **The Resolution / Exit (Conclusion):** How does the thread end?
   - Concession / intellectual humility (*"Fair point, I hadn't seen it that way"*).
   - Defiance / doubling down into ideological rigidity.
   - Emotional retreat / cold dismissal (*"Whatever, let's drop it"*).
   - Deflection into humor or self-deprecation.

---

### Phase 4: Full Spectrum Life Spheres Audit (A–F)

Examine the subject's conduct across the 6 foundational spheres of life:

#### A. Social Matrix & Friendship Dynamics
- **Friendship Paradigm:** Do they view friends as authentic confidants, an admiring audience, or utilitarian assets? Do they maintain an exclusive inner circle while keeping others at arm's length?
- **Loyalty vs. Door-Slamming:** Do they repair relational fractures, or do they permanently cut ties (*door-slam*) upon the first perceived disloyalty?
- **Envy vs. Compersion:** How do they react to peers' achievements? Genuine pride vs. passive-aggressive minimization, envy, or anxious comparison.
- **Confidentiality:** Do they guard secrets faithfully, or instrumentalize gossip?

#### B. Work, Ambition & Authority Relations
- **Hierarchy & Power:** Do they instinctively rebel against superiors and corporate structures, or act as hyper-conscientious perfectionists desperate for validation?
- **Agency vs. Imposter Syndrome:** Do they possess genuine self-efficacy, or suffer chronic feelings of fraudulence despite external achievements?
- **Money & Material Success:** Is wealth a measure of security, a shield of autonomy, social status, or a subconscious source of guilt?

#### C. Worldview, Politics & Cognitive Debate Style
- **Socio-Political Beliefs:** Views on governance, taxation, individual liberty, tradition, religion, and social conventions.
- **Cognitive Style in Debate:** Do they lean on empirical evidence and formal logic, or emotional appeal and moral superiority? Do they respect ideological opponents or dehumanize them?

#### D. Family Roots & Parental Imprints
- **Parental Imprints:** Mother and father archetypes; presence of conditional love, harsh discipline, or emotional neglect.
- **Sibling Dynamics & Parentification:** Were they forced to take on adult caretaker roles prematurely?
- **Generational Traps:** Did they witness an entrapped or unhappy parental marriage? How does this dictate their fear of commitment?

#### E. Romantic Attachment & Deactivating Strategies
- **Attachment Style Diagnosis:** Explicitly classify according to Bowlby / Ainsworth / Bartholomew:
  - *Secure:* Balances intimacy and autonomy with ease; trusts directly.
  - *Anxious-Preoccupied:* Chronic abandonment fears, overthinks response delays, demands constant reassurance.
  - *Dismissive-Avoidant:* High defensive self-reliance, deactivating strategies (finding flaws, emotional shutdown).
  - *Fearful-Avoidant (Disorganized):* Desires closeness but fears engulfment; push-pull dynamics; guarded exterior until bonded, then intense anxiety.
- **Deactivating Strategies:** Checklist perfectionism, sabotage when intimacy deepens.

#### F. Passions, Aesthetics & Solitude
- **Authentic Obsessions:** What topics make their eyes light up once social and professional masks are discarded?
- **Restoration Modes:** How do they recharge? (Solitude, gaming, literature, physical exertion, technical tinkering).
- **Aesthetic Sensibility:** What art, design, or ideas inspire them?

---

### Phase 5: Forensic Psychological & Behavioral Dimensions

Conduct targeted forensic investigations across these 11 specialized layers:

1. **Conspicuous Absences (The Unspoken Matrix):**
   - Audit topics that are suspiciously absent over multi-year logs (e.g. total silence regarding a living parent, complete omission of emotional vocabulary like *"kocham"* or *"przykro mi"*, refusal to discuss finances).
2. **Linguistic Fingerprint & Register (Idiolect):**
   - *Code-switching:* Clinical, formal distancing during conflict vs. colloquial warmth during safety.
   - *Masking emojis & punctuation:* Using laugh emojis as emotional shields (*"No trudno 😂"*), ellipses, defensive irony.
   - *Cognitive catchphrases:* Recurring verbal anchors (*"to jest absurd"*, *"nie moja sprawa"*, *"zasada jest prosta"*).
3. **Temporal Evolution (Film vs. Static Statue):**
   - Compare early months vs. late months. Did defense mechanisms soften or calcify? How did initiative balances in `--gaps` migrate?
4. **Internal Contradictions & Fractures (Words vs. Actions):**
   - Juxtapose declared values against recorded conduct (e.g. preaching emotional honesty while retreating into sulking silence).
5. **Relational Dynamics & Power Balance:**
   - Linguistic accommodation: who mirrors whose lexicon? Who occupies the teacher/mentor role vs. student/validator?
6. **Narrative Self-Presentation Archetypes:**
   - Detect the recurring archetype in anecdotes: **The Hero** (high agency, conquering odds), **The Victim** (external locus of control, victimized by systems), **The Comedian** (converting pain into stand-up), or **The Detached Observer** (clinical alien studying humanity).
7. **Accountability Index & Apology Mechanics:**
   - Genuine ownership (*"Przepraszam, to był mój błąd"*) vs. non-apologies (blame-shifting, conditional *"Przepraszam JEŚLI poczułeś się urażony"*, joke deflections).
8. **Boundary Testing & Reactions to Hearing 'NO':**
   - What happens when a dialogue partner sets a hard boundary (*"Nie"* / refusing a request)? Mature acceptance vs. guilt-tripping, wheedling, or passive-aggressive punishment.
9. **'Nighttime Truth' vs. Daytime Armor (Prefrontal Fatigue Window):**
   - Contrast messages sent during peak daytime composure with late-night messages (23:00–04:00). Catch the moments where self-monitoring fails.
10. **Behavioral MBTI (Strictly Observational):**
    - **E vs. I:** Burst-based live thinking (rapid unprompted message trains) vs. delayed, consolidated paragraph synthesis after prolonged processing.
    - **S vs. N:** Chronological facts, physical specs, concrete details vs. conceptual frameworks, patterns, future projections, metaphors.
    - **T vs. F:** Primacy of impersonal truth and logical consistency vs. relational impact, empathy, and emotional resonance.
    - **J vs. P:** Need for structural closure, schedules, and definitive verdicts vs. keeping options fluid, delaying finality.
11. **Operational User Manual & Actionable Playbook:**
    - Synthesize pragmatic rules for interacting with this individual (see below).

---

## 3. Modular Drafting & Automated Assembly

To prevent context truncation, preserve precision, and allow targeted editing, the agent **drafts the report in modular section files**, then compiles them with the assembly utility.

### Recommended Drafting Layout:
The agent writes individual section files into a temporary working folder (e.g., `reports/<subject>_sections/` outside `project/`):
- `00_dossier_and_timeline.md`: Motto, Case Header, Identity Dossier, Chronological Life Timeline.
- `01_cast_of_characters.md`: Full relational constellation with roles, topics, and emotional stances.
- `02_cognitive_and_mbti.md`: Behavioral MBTI analysis and intellectual debate style.
- `03_social_and_worldview.md`: Spheres audit (Friends, Work/Authorities, Politics/Philosophy, Passions).
- `04_relational_and_attachment.md`: Attachment style classification, dating history, and silence dynamics.
- `05_shadow_and_boundaries.md`: Contradictions, accountability, boundary testing, night vs. day.
- `06_operational_manual.md`: Blind spots, triggers, unspoken need, communication protocols, Summary Matrix.

### Assembly Execution:
```bash
python3 project/scripts/assemble_report.py --sections-dir reports/<subject>_sections/ -o reports/<subject>_profile.md
```
The script validates code fence closure, ensures formatting integrity, and generates an automated Table of Contents.

---

## 4. Document Architecture & Formatting Standards

Every thematic chapter within the report MUST follow the **Thesis-First Framework**:

```markdown
## [Number]. [Clear, Descriptive Title of the Trait, Dynamic, or Diagnosis]

### 📌 The Core Thesis
[2–3 bold, definitive sentences stating the psychological insight upfront. 
The reader grasps the entire finding simply by reading this thesis.]

### 🧠 In-Depth Psychological Analysis
[Detailed forensic commentary connecting childhood roots, defense mechanisms, and cognitive patterns 
to observed adult behavior. Explicitly name the underlying psychological mechanisms.]

### 🔍 Verbatim Evidence & Case Studies
[Direct quotes from chat logs with exact dates (YYYY-MM-DD) and conversational context.
Format quotes in markdown blockquotes.]

### 💡 Key Takeaway
[1–2 punchy sentences summarizing the operational insight.]
```

---

## 5. Report Structure Checklist

A complete personality profile must contain:

1. **Opening Motto:** Verbatim quote encapsulating their core philosophy or existential longing.
2. **Case File Header:** Name/alias, observed Behavioral MBTI, diagnosed Attachment Style, date range analyzed, total volume.
3. **Biographical Dossier & Life Timeline:** Reconstructed origin story, formative milestones, turning points.
4. **Cast of Characters:** Comprehensive table and profile of recurring third parties and the subject's stance toward them.
5. **Core Thematic Chapters (Thesis-First):**
   - Behavioral MBTI & Cognitive Architecture.
   - Socio-Political Philosophy & Intellectual Debate Style.
   - Social Circle & Friendship Dynamics (Door-slams, loyalty, envy).
   - Work, Ambition & Authority Relations.
   - Romantic Attachment & Emotional Defense Mechanisms.
   - Internal Contradictions, Accountability & Boundary Testing.
   - The Prefrontal Fatigue Window ("Nighttime Truth").
6. **Operational User Manual (Actionable Playbook):**
   - **Blind Spots:** What they fail to see about their own behavior.
   - **Emotional Triggers (Red Buttons):** Specific words and scenarios that spark instant defensive regression or rage.
   - **Unspoken Core Need:** The primary emotional hunger they yearn for but never voice.
   - **Communication Protocols:** Concrete rules on how to de-escalate, persuade, and resolve conflict (What NEVER to do / What ALWAYS works).
   - **Statement Reliability Index:** Where their commitments are ironclad vs. where their words are wishful thinking.
7. **Summary Matrix:**
   A structured markdown comparison table:

```markdown
## Summary Matrix

| Psychological Dimension | Observable Behavior | Formative Root & Inner Meaning |
| :--- | :--- | :--- |
| **Behavioral MBTI** | [e.g., INTJ (Delayed synthesis, abstract modeling, logical priority, high closure)] | [e.g., Early isolation; reliance on intellectual frameworks for safety] |
| **Attachment Style** | [e.g., Fearful-Avoidant (Deactivating armor until deeply bonded)] | [e.g., Witnessing mother's trapped marriage; public disciplinary humiliation] |
| **Social Stance** | [e.g., Selective inner circle; swift door-slamming upon perceived slight] | [e.g., Defense against betrayal; refusing vulnerability with low-stakes contacts] |
| **Accountability** | [e.g., Conditional apologies ("Przepraszam JEŚLI"); intellectualization] | [e.g., Perfectionist superego where admitting fault triggers shame] |
| **Unspoken Need** | [e.g., Longing for unconditional acceptance without having to perform] | [e.g., Childhood love conditioned on exceptional performance] |
```

---

## 6. Output Language Standard (Default Polish Delivery)

- **Mandatory Default Output Language:** The generated personality profile report (and all modular section files drafted by the agent) **MUST be written in Polish by default**.
- **User Language Selection:** Only when the user explicitly requests another language (e.g., *"translate this profile to English"* or *"generate in English"*) should the agent deliver the profile in that requested language.
- **Specification vs. Output Separation:** All skill definitions, rules, scripts, and documentation inside `project/` remain strictly in English, but the analytical product delivered to the user is in Polish by default.
