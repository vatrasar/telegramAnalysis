---
name: personality-analysis
description: >-
  Conducts deep, thesis-driven psychological and personality profiling from longitudinal chat logs
  and transcripts. Uses an investigative detective/profiler mindset to reconstruct biographical
  dossiers, diagnose Big Five (OCEAN) traits and attachment styles, audit all intensive
  discussions, map the cast of characters, analyze life spheres (friends, work, worldview), detect
  internal contradictions and unconscious blind spots, and generate actionable operational manuals.
  Formatted in a modular Thesis-First architecture.
---

# Personality Profiling & Behavioral Intelligence Skill

This skill defines the methodology, investigative mindset, and modular document architecture for generating forensic-grade psychological portraits from longitudinal chat archives (often spanning tens of thousands of messages across multiple years).

It transforms raw message logs into an exhaustive psychological dossier that deciphers **who the person actually is**, traces their **formative roots**, exposes their **unconscious defense mechanisms**, classifies their **Big Five (OCEAN) Profile** and **Attachment Style**, maps their **Relational Constellation**, and compiles an **Actionable Operational User Manual** for interacting with them.

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
4. **Bidirectional Context & Epistemic Traceback (Next-Turn Proof Procedure):**
   - **Look Back (Origin Check):** When a strong factual claim is made about a third party, trace back through the archive. Is it grounded in prior factual disclosures, or is it a spontaneous inference, hyperbole, or conversational provocation?
   - **Look Ahead (Next-Turn Proof):** Always examine turns $N+1$ to $N+5$. If the interlocutor immediately refutes, corrects, or jokes away the statement, never record that claim as established fact.
   - **Epistemic Authority vs. False Symmetry:** Give primary evidentiary weight to the participant who directly witnessed external interactions. Do not create false symmetry ("Person A says X, Person B says Y") when an external observer's guess is falsified by the primary witness with direct evidence.
5. **The Actuation Gate (Modality & Irrealis vs. Realis):**
   - Strictly distinguish between wishes/offers (*irrealis*) and executed historical facts (*realis*). Verbs of intent or proposal (*"offered"*, *"insisted on accepting"*, *"wanted to"*, *"planned"*, *"dreamed"*, *"chciał"*) must never be converted into biographical reality or professional titles without proof of actual execution. Always audit the subsequent resolution of episodic offers or plans.
6. **The Evidentiary Pruning Principle (Strict Omission of Unaddressed Topics):**
   - The archive reflects what the participants actually discussed, not an exhaustive inventory of every human domain. If a specific life sphere, practical dimension, or topic (e.g. sports, pets, vacations, domestic cleaning) was simply never discussed in the logs, **completely omit that point or topic from the report**.
   - **Absolute Ban on Placeholder Disclaimers:** Never write empty sections or negative boilerplate (e.g., *"Brak informacji na temat sportu"*, *"Temat ten nie był poruszany w rozmowie"*, *"No data available in archive"*).

---

## 2. Multi-Stage Investigative Workflow

> [!IMPORTANT]
> **Mandatory Ingestion & Indexing Prerequisite:**
> Before initiating Phase 1 or Phase 2, the agent must ensure that:
> 1. Pre-flight verification (`project/scripts/setup_config.py`) succeeded with Exit Code 0.
> 2. Analytical database was built cleanly without cross-subject contamination (`project/scripts/db_builder.py <file> -o chat.db --clean` or via a dedicated subject database `-o chat_<subject>.db`).
> 3. Semantic vector embeddings were generated (`project/scripts/vector_indexer.py --db chat.db --index`).
> 4. System-1 dialogue thread triage was executed (`project/scripts/triage_threads.py --db chat.db`).
> Deep psychological exploration, semantic search (`--semantic`), and quiet disclosure retrieval strictly depend on indexed vector embeddings and System-1 triage; never skip indexing or triage.

```
[Phase 1: Macro-Recon & Triage Anomalies] 
   └── --stats, --timeline, --gaps, --burning-days, --anomalies-only, --triaged-threads
[Phase 2: Biographical Dossier & Cast of Characters]
   └── Chronological Timeline + Relational Constellation Mapping
[Phase 3: All Intensive Discussions & Ideology]
   └── 3-Point Thread Inspection (Trigger → Core Debate → Resolution)
[Phase 4: Full Spectrum Life Spheres & Forensic Dimensions]
   └── Spheres A–F + 11 Forensic Psychological Layers (Big Five OCEAN)
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
6. **System-1 Triage & Quiet Disclosures (`--triaged-threads`, `--triage-status`):**
   - Inspect threads pre-filtered by the System-1 triage engine (`project/scripts/triage_threads.py`).
   - Rescues low-volume, high-salience psychological disclosures ("quiet disclosures", e.g. 2-3 message admissions of trauma, grief, or relational fractures) that pure word-count heuristics discard, while pruning 70–80% of routine logistical noise.

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
>    - **Primary Subject:** Query for definitive negative milestones (e.g. `boyfriend OR chłopak OR ex OR first time OR never OR until`). An explicit quote such as *"I didn't even have a boyfriend until last year"* is an iron-clad falsification gate that instantly disqualifies earlier romantic relationships.
>    - **Key Entity Baseline Audit:** Extend falsification queries to core third parties (parents, partners). Before recording a permanent role or profession, query baseline statements (e.g. `mother AND (work OR job OR housewife OR pracuj OR dom)`). A direct declaration like *"my mother is not working"* overrides episodic stories about offers.
>    - Never synthesize continuous multi-year spans (e.g. "2020–2023") by interpolating between disconnected mentions. Fact-pin every timeline claim with supporting message IDs (`[#ID | YYYY-MM-DD]`).
> 6. **The Actuation Gate & Resolution Check Protocol:**
>    - **Modality vs. Fact:** Never convert modal verbs, job offers, or desires (*offered*, *insisted on accepting*, *wanted*, *planned*, *applied*) into established biographical facts.
>    - **Resolution Audit:** When a high-gravity opportunity or life change is mentioned (job offer, engagement, move, degree application), trace the thread forward or query the aftermath to determine whether it was realized, blocked, or abandoned.
>    - **Conditional Psychological Crucible Recording:** If (and only if) an unrealized trajectory or thwarted ambition caused documented interpersonal tension or emotional wounds (e.g. mother's blocked kindergarten directorship), record it under that character's psychological dynamics / sources of friction. **Do not force this field if no such event occurred**, and **never confuse an unrealized dream with actual occupational status**.

#### 2. Cast of Characters (Relational Constellation)
Systematically audit all significant recurring third parties mentioned in the logs:
- **Family Members:** Parents, siblings, grandparents, children, in-laws.
- **Friends & Acquaintances:** Close confidants vs. superficial social contacts (identified by name/nickname).
- **Romantic Partners:** Current partner, ex-partners, romantic prospects.
- **Professional Figures:** Bosses, mentors, coworkers, clients.
- **Rivals / Adversaries:** Individuals with whom the subject entered sharp dispute or estrangement.

For each figure, determine:
- **Exact Identification:** Distinct name/alias, active dates, and context of meeting. If multiple figures share a nationality or generic label, list them as explicitly separate entities.
- **Their Role & Verified Status:** Authority figure, emotional anchor, dependent responsibility, rival, or trigger. Verified occupational or marital status grounded in actual practice (not unrealized offers).
- **Recurring Themes & Dynamics:** What situations invoke this person? If an unrealized trajectory or thwarted ambition occurred and generated acute emotional conflict, capture it here as a psychological dynamic.
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

### Phase 4: Full Spectrum Life Spheres & Behavioral Dimensions Audit (A–F)

> [!IMPORTANT]
> **Evidentiary Threshold & Omission Protocol for Life Spheres:**
> Spheres A–F and their sub-dimensions represent an investigative search guide, **NOT a mandatory list of headers to generate**.
> - If targeted queries (`--semantic`, keyword searches) yield no mentions or substantive discussions on a topic (e.g. the interlocutors never discussed sports, pets, travel, or domestic order), **completely omit that point/topic from the report**.
> - **Strict Prohibition on Placeholders:** Never generate empty sections or disclaimers such as *"Brak informacji o sporcie"* or *"No data available"*. Only synthesize sections backed by actual conversational evidence.

Examine the subject's conduct across the 6 foundational spheres of life, ensuring thorough forensic probing into both existential dynamics and everyday practical lifestyle patterns:

#### A. Social Matrix & Friendship Dynamics
- **Authentic Friends vs. Superficial Contacts:** Does the subject possess a genuine circle of close, trusted friends, or are social contacts primarily superficial acquaintances, colleagues, or online contacts?
- **Social Cadence & Meeting Frequency:** How often do they actually meet friends in real life? Are offline hangouts frequent, routine, sporadic, or actively avoided in favor of digital-only interactions?
- **Shared Social Activities:** How do they spend time with friends? (E.g., house visits, dining/pub outings, shared gaming sessions, sports/outdoor activities, artistic/intellectual discussions, or mutual venting).
- **Altruism & Helping Others (Prosocial Stance):** Do they genuinely enjoy helping others, offering spontaneous assistance, time, advice, or practical aid? Is their helpfulness selfless and empathic, or is it transactional (expecting payback), driven by a savior/caretaker complex, or avoided altogether?
- **Friendship Paradigm & Boundaries:** Do they view friends as authentic confidants, an admiring audience, or utilitarian assets? Do they maintain an exclusive inner circle while keeping others at arm's length?
- **Loyalty vs. Door-Slamming:** Do they repair relational fractures, or do they permanently cut ties (*door-slam*) upon the first perceived disloyalty?
- **Envy vs. Compersion & Confidentiality:** How do they react to peers' achievements? Genuine pride vs. passive-aggressive minimization, envy, or anxious comparison. Do they guard secrets faithfully or instrumentalize gossip?

#### B. Professional Sphere, Work Ethic & Financial Psychology
- **Work Ethic & Diligence (Hard Worker vs. Slacker):** Are they a conscientious grinder/workaholic ("pracuś"), driven by perfectionism and duty, or do they slack off ("obijanie się"), procrastinate, coast, or do the bare minimum?
- **Aspirations, Ambitions & Plan Execution Track Record:**
  - *Declared Ambitions & Long-term Vision:* What scale of ambition do they voice (career milestones, creative projects, entrepreneurial ventures, educational pivots, relocation)?
  - *Follow-Through vs. Phantom Declarations:* Over the longitudinal timeline, do they systematically execute declared plans, hit milestones, and follow through, OR do their ambitious declarations evaporate into empty words, perpetual postponement, and wishful thinking?
  - *Specific Unfulfilled Ambitions & Abandoned Goals (The Catalogue of Unrealized Dreams):*
    - The profiler must explicitly identify, itemize, and name the **concrete unfulfilled ambitions, abandoned ventures, uncompleted qualifications/degrees, dropped projects, or deferred life paths** revealed across the archive (e.g. *"wanted to launch a startup but never did"*, *"planned to study abroad"*, *"abandoned writing a book/creative work"*, *"dreamed of switching to medicine/IT but stayed in a safe job"*).
    - For each identified unfulfilled ambition, investigate:
      1. What was the exact envisioned ambition and when was it declared?
      2. At what stage did execution stall or derail?
      3. What was the true blocker (e.g., perfectionist paralysis, fear of public failure, lack of financial runway, loss of novelty, partner/parental discouragement)?
      4. Does it linger as an open psychic wound, a chronic source of melancholy/regret ("what could have been"), or was it maturely mourned and replaced?
  - *Coping with Unfulfilled Ambitions & Failure:* How do they handle stalled projects or unrealized dreams? Do they exhibit mature self-reflection and realistic recalibration, or retreat into externalized blame (blaming systems, bosses, lack of time) and rationalization?
- **Team Player vs. Lone Wolf:** Are they a cooperative team player who communicates constructively, shares credit, and fosters group alignment, or a fiercely autonomous lone wolf who distrusts collective efforts and prefers working strictly in a silo?
- **Team Role & Leadership Dynamics:** Are they a natural leader, project initiator, and decision-maker who takes responsibility, or do they prefer being an individual contributor / task executor who follows explicit orders and avoids organizational exposure?
- **Hierarchy & Power:** Do they instinctively rebel against superiors and corporate structures, or act as hyper-conscientious perfectionists desperate for validation?
- **Agency vs. Imposter Syndrome:** Do they possess genuine self-efficacy, or suffer chronic feelings of fraudulence despite external achievements?
- **Financial Psychology & Money Management:**
  - *Frugality vs. Spendthrift Habits:* Are they disciplined savers, bargain hunters, and frugal planners, or impulsive spenders, status buyers, or lavish spendthrifts?
  - *Attitude Toward Wealth & Material Security:* Is money an instrument of safety, a shield of autonomy, social status, or a subconscious source of guilt? How do they handle everyday budgeting, luxury purchases, debts, investments, or treating others?

#### C. Worldview, Politics & Technology Stance
- **Socio-Political Beliefs:** Explicit political orientation (conservative, liberal, libertarian, left-wing, centrist, or apolitical/disillusioned), stance on governance, taxation, civic duties, individual liberties, tradition, and religion.
- **Attitude Toward Artificial Intelligence & Modern Technology:**
  - *AI & Tech Posture:* Are they enthusiastic early adopters, pragmatic utilitarians, philosophical skeptics, or apprehensive about AI (automation, ethical risks, epistemic decline, dehumanization)?
  - *Practical Tech Usage:* Do they embrace modern digital tools and AI assistants in their daily workflow and reasoning, or do they express resistance to technological shifts?
- **Cognitive Style in Debate:** Do they lean on empirical evidence and formal logic, or emotional appeal and moral superiority? Do they respect ideological opponents or dehumanize them?

#### D. Family Roots, Parental Imprints & Domestic Environment
- **Parental Imprints:** Mother and father archetypes; presence of conditional love, harsh discipline, or emotional neglect.
- **Sibling Dynamics & Parentification:** Were they forced to take on adult caretaker roles prematurely?
- **Generational Traps:** Did they witness an entrapped or unhappy parental marriage? How does this dictate their fear of commitment?
- **Approach to Domestic Order & Living Space:**
  - *Orderliness vs. Chaos:* Meticulous cleanliness and structured minimalism vs. high clutter tolerance, disorganization, or chronic mess.
  - *Domestic Environment as Psychological Mirror:* How does their living space reflect their internal state? (E.g., compulsive cleaning as a stress-relief mechanism vs. neglecting environment during depressive/overwhelmed episodes).

#### E. Romantic Attachment & Deactivating Strategies
- **Attachment Style Diagnosis:** Explicitly classify according to Bowlby / Ainsworth / Bartholomew:
  - *Secure:* Balances intimacy and autonomy with ease; trusts directly.
  - *Anxious-Preoccupied:* Chronic abandonment fears, overthinks response delays, demands constant reassurance.
  - *Dismissive-Avoidant:* High defensive self-reliance, deactivating strategies (finding flaws, emotional shutdown).
  - *Fearful-Avoidant (Disorganized):* Desires closeness but fears engulfment; push-pull dynamics; guarded exterior until bonded, then intense anxiety.
- **Deactivating Strategies:** Checklist perfectionism, sabotage when intimacy deepens.

#### F. Leisure, Sports, Travel, Vacations & Relationship with Animals
- **Free Time & Hobbies (Restoration Modes):** How do they actively choose to spend discretionary time? Passive consumption (scrolling, streaming) vs. active passions (gaming, reading, creative arts, physical sports, technical tinkering, solo contemplation).
- **Sports & Physical Activity:**
  - *Exercise Habits & Preferences:* Do they practice sports or physical training (e.g., gym, running, swimming, cycling, team sports, martial arts, fitness classes)? Do they follow/watch sports as a spectator?
  - *Function of Physical Culture:* Is exercise a discipline, a stress-relief mechanism, an aesthetic body-image drive, or do they express active aversion/apathy toward physical exertion (sedentary lifestyle)?
- **Vacation & Holiday Style:** How do they spend vacations and time off?
  - *Style & Structure:* Rigidly planned itineraries vs. spontaneous drifting; resort comfort vs. adventurous exploration; traveling solo vs. with partners/friends.
  - *Psychological Decompression:* Can they genuinely unplug from work and duties, or do they carry anxiety and hyper-vigilance into their time off?
- **Travel Motivations & Modus Operandi (Why and How They Travel):**
  - *Drivers:* Why do they travel (or why do they avoid it)? Driven by cultural curiosity, escape from routine, wanderlust, romantic getaways, or staying grounded as a committed homebody.
  - *Pattern:* Domestic getaways vs. international travel, high-frequency nomadism vs. rare, carefully curated journeys.
- **Relationship with Animals & Pets:**
  - *Pet Ownership & Affection:* Do they have pets (dogs, cats, etc.), desire pets, or avoid them?
  - *Emotional Bond & Empathy:* How do they interact with and talk about animals? Animal empathy serves as a potent window into their instinctual warmth, capacity for unconditional care, or sensory/cleanliness boundaries.

---

#### Targeted Search Lexicon for Lifestyle & Behavioral Probing

To investigate these practical behavioral spheres effectively, the agent executes targeted queries using `project/scripts/query_chat.py` (combining semantic search `--semantic` with keyword filters `-s`):

| Analytical Target | Polish Query Keywords | English / Concept Query Keywords |
| :--- | :--- | :--- |
| **Domestic Order & Cleanliness** | `sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać` | `cleaning OR mess OR tidy OR clutter OR chore OR apartment` |
| **Friends, Social Cadence & Meetups** | `znajomi OR przyjaciel OR kumpel OR wyjście OR piwo OR spotkać OR na żywo` | `friends OR hang out OR meet up OR drinking OR socializing` |
| **Altruism & Helping Others** | `pomóc OR pomoc OR pomagam OR przysługa OR wsparcie OR poradzić OR wyręczyć` | `help OR helping OR favor OR support OR altruism OR assist OR volunteer` |
| **Work Ethic & Team Role** | `praca OR szef OR nadgodziny OR leniuchować OR obijać OR awans OR lider OR polecenia` | `work ethic OR boss OR overtime OR slacking OR leader OR task` |
| **Aspirations & Plan Execution** | `planuję OR plany OR cel OR marzenie OR ambicja OR projekt OR zamierzam OR postanowiłem OR zrealizować OR rzucić` | `plan OR goal OR ambition OR project OR intention OR execute OR follow through OR milestone` |
| **Unfulfilled Ambitions & Abandoned Plans** | `chciałem być OR marzyłem o OR miałem plan OR zrezygnowałem OR nie wyszło OR odpuściłem OR żałuję OR rzuciłem OR niedokończone OR planowałem` | `used to want OR dreamed of OR had a plan OR gave up OR didn't work out OR dropped out OR regret OR abandoned OR unfinished` |
| **Team Player vs. Lone Wolf** | `zespół OR drużyna OR współpraca OR gracz zespołowy OR razem OR samotnik OR indywidualista` | `teamwork OR team player OR collaboration OR cooperative OR lone wolf` |
| **Sports & Physical Activity** | `sport OR siłownia OR bieganie OR biegam OR trening OR ćwiczyć OR rower OR basen OR mecz` | `sports OR gym OR workout OR running OR fitness OR exercise OR training` |
| **Leisure & Hobbies** | `czas wolny OR hobby OR grać OR seriale OR czytać OR odpoczynek OR nudzi mi się` | `free time OR hobby OR gaming OR watching OR reading OR bored` |
| **Political & Societal Views** | `polityka OR wybory OR rząd OR podatki OR partia OR państwo OR wolność` | `politics OR elections OR government OR taxes OR freedom OR laws` |
| **Vacations & Holidays** | `urlop OR wakacje OR wyjazd OR odpocząć OR plaża OR hotel OR wolne w pracy` | `vacation OR holiday OR summer trip OR resort OR time off` |
| **AI & Modern Technology** | `AI OR sztuczna inteligencja OR ChatGPT OR model OR robot OR technologia` | `AI OR artificial intelligence OR LLM OR automation OR tech` |
| **Animals & Pets** | `pies OR piesek OR kot OR kotek OR zwierzak OR pupil OR schronisko` | `dog OR puppy OR cat OR kitten OR pet OR animal OR shelter` |
| **Travel (Motivations & Style)** | `podróż OR zwiedzać OR samolot OR lot OR zagranica OR walizka OR wycieczka` | `travel OR trip OR flight OR abroad OR sight-seeing OR journey` |
| **Money Management & Spending** | `pieniądze OR oszczędzać OR wydać OR drogo OR tanio OR kupić OR finanse OR kredyt` | `money OR save OR spend OR budget OR splurge OR frugal OR debt` |

---

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
10. **Cognitive Processing & Information Habits:**
    - Synthesis vs. Live Bursts: Deliberate, delayed paragraph synthesis after prolonged processing vs. rapid unprompted message trains / thinking out loud.
    - Conceptual vs. Concrete: Systematic frameworks, metaphorical models, and abstract patterns vs. immediate concrete facts and physical specs.
    - Epistemic vs. Relational Orientation: Primacy of empirical truth and logical consistency vs. relational harmony and emotional soothing.
    - Deliberation vs. Closure: Fluid delay of finality and exploring alternatives vs. high need for immediate structured closure and verdicts.
    *(Note: Do not classify or assign 4-letter MBTI types. Focus on empirical cognitive habits and behavioral traits.)*
11. **Big Five Personality Dimensions (OCEAN - Observational Profiling):**
    Systematically evaluate and estimate the subject's spectrum across all 5 dimensions (Very Low / Low / Moderate / High / Very High or spectrum tendencies), anchored in longitudinal conversational evidence:
    - **O — Openness to Experience (Otwartość na doświadczenie):**
      - *High:* Intellectual curiosity, philosophical inquiry, artistic/aesthetic appreciation, passion for unconventional models, exploration through travel (seeking cultural novelty and foreign horizons), enthusiasm and experimentation with AI and cutting-edge technologies, rich metaphorical idiolect.
      - *Low:* Pragmatic adherence to immediate concrete reality, preference for conventional routines, homebody orientation avoiding travel or novelty, dismissal of abstract hypothetical speculation and tech disruptions.
    - **C — Conscientiousness (Sumienność):**
      - *High:* High structural discipline, strong work ethic ("pracuś", high diligence, taking ownership or perfectionism), systematic execution of declared plans and ambitions over time (high follow-through, milestones achieved), physical fitness consistency (regular workouts or sports routine), domestic cleanliness and orderliness (intolerance of clutter/mess), disciplined financial management (budgeting, frugality, long-term saving), organized message formatting (bullet points, clear paragraphs, syntactic precision), reliable follow-through on declared tasks.
      - *Low:* Spontaneous stream-of-consciousness bursts, disorganization, chronic procrastination or slacking at work ("obijanie się"), recurring ambitious declarations without real-world execution (phantom plans, wishful thinking, abandoned projects), sedentary physical habits, high tolerance for domestic mess and clutter, impulsive spending or lack of financial planning, fluid boundaries, abandoning threads mid-thought.
    - **E — Extraversion (Ekstrawersja):**
      - *High:* High conversational initiative, low latency in reconnecting after gaps (`--gaps`), external processing (thinking out loud via message bursts), expressive emotional valence, active desire for social contact, frequent offline meetups with friends, preference for group activities, team sports, and high-energy social gatherings.
      - *Low (Introversion):* Solitary recharge, deliberate paragraph synthesis, comfort with prolonged silence, high selectivity in dialogue partners, rare or curated offline meetups, conversational energy depleting during group chatter, preference for solo hobbies, solo fitness (running, home workouts), and solitary travel/vacation retreats.
    - **A — Agreeableness (Ugodowość):**
      - *High:* Empathic validation, active de-escalation of interpersonal tension, prosocial cooperation, natural empathy and warmth toward animals and vulnerable beings, altruism and genuine joy in helping others, collaborative team-player mindset (seeking mutual win-win over asserting dominance), willingness to accommodate and soothe, avoidance of harsh friction.
      - *Low:* Argumentative debate stance, intellectual skepticism, blunt confrontation, indifference or instrumental stance toward others/animals, lone-wolf mentality (resisting team dependence), conditional or reluctant helping, low fear of relational rupture, competitive drive in ideological clashes, skepticism of other people's motives.
    - **N — Neuroticism / Emotional Stability (Neurotyczność / Stabilność emocjonalna):**
      - *High Neuroticism (Low Stability):* Heightened emotional volatility, rumination, acute sensitivity to perceived slights, vulnerability decompensation during late-night fatigue ("Nighttime Truth"), financial anxiety and catastrophic money fears, inability to relax on vacations/holidays, chronic anxiety spikes on anomalous peak days (`--burning-days`).
      - *Low Neuroticism (High Stability):* Emotional poise under pressure, stoic baseline affect, resilient recovery from conflict, resistance to spiral thinking, even-tempered interaction style, relaxed attitude toward uncertainties.
    - *Triangulation & Synergies:* Cross-examine how Big Five traits interact with Attachment Style and relational defenses (e.g. Introversion + Low Agreeableness + High Openness fueling an intellectualized detached critic stance; High Neuroticism fueling Anxious/Disorganized Attachment deactivating spirals).
12. **Operational User Manual & Actionable Playbook:**
    - Synthesize pragmatic rules for interacting with this individual (see below).

---

## 3. Modular Drafting & Automated Assembly

To prevent context truncation, preserve precision, and allow targeted editing, the agent **drafts the report in modular section files**, then compiles them with the assembly utility.

### Recommended Drafting Layout:
The agent writes individual section files into a temporary working folder (e.g., `reports/<subject>_sections/` outside `project/`):
- `00_dossier_and_timeline.md`: Motto, Case Header, Identity Dossier, Chronological Life Timeline.
- `01_cast_of_characters.md`: Full relational constellation with roles, topics, and emotional stances.
- `02_cognitive_architecture_and_big_five.md`: Cognitive architecture, Big Five (OCEAN) profile estimation, and intellectual debate style.
- `03_social_and_worldview.md`: Spheres audit (Friends, Social Cadence & Altruism/Helping, Work Ethic, Ambitions & Catalogue of Unfulfilled Goals, Team Player vs. Lone Wolf, Money Management, Politics & AI, Domestic Order, Sports/Fitness, Vacations, Travel & Animals). *Note: Include only spheres and sub-topics discussed in the logs; omit unaddressed topics completely without placeholder disclaimers.*
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

> [!NOTE]
> **Dynamic Structural Adaptability (Strict Omission Rule):**
> The thematic chapters listed below represent the full spectrum of potential investigative domains to explore.
> - If a specific topic, sphere, or sub-dimension (e.g., sports/athletics, relationship with animals, specific travel experiences, domestic cleaning habits) was **never discussed in the chat logs, completely omit that sub-topic or chapter from the report**.
> - **Never include empty sections, disclaimers, or "no data available" boilerplate** (e.g. *"Brak informacji o sporcie"*, *"Temat nie był poruszany"*).
> - Dedicated lifestyle chapters should only be included for topics that actually emerged in the conversations.

A complete personality profile must contain:

1. **Opening Motto:** Verbatim quote encapsulating their core philosophy or existential longing.
2. **Case File Header:** Name/alias, diagnosed Attachment Style, Big Five (OCEAN) summary profile (e.g., O: High, C: High, E: Low, A: Low-Moderate, N: High), date range analyzed, total volume.
3. **Biographical Dossier & Life Timeline:** Reconstructed origin story, formative milestones, turning points.
4. **Cast of Characters:** Comprehensive table and profile of recurring third parties and the subject's stance toward them.
5. **Core Thematic Chapters (Thesis-First):**
   - Big Five (OCEAN) Cognitive Architecture & Processing Habits (including Conscientiousness, Orderliness & Cleanliness).
   - Socio-Political Philosophy, Stance on AI/Technology & Intellectual Debate Style.
   - Social Circle, Friendship Dynamics, Social Cadence & Altruism (Offline vs. online frequency, shared activities, helping behavior, loyalty, door-slams).
   - Work Ethic, Ambitions, Catalogue of Specific Unfulfilled Ambitions & Plan Execution (Follow-Through vs. Phantom Declarations), Team Role (Leader vs. Executor, Team Player vs. Lone Wolf) & Money Management (Frugal vs. Spendthrift).
   - Leisure, Sports/Physical Activity, Vacations, Travel Motivations & Relationship with Animals.
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
| **Big Five (OCEAN)** | [e.g., O: High, C: High, E: Low, A: Low-Moderate, N: High (Volatile)] | [e.g., Intellectualization and perfectionism as armor against emotional chaos] |
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
