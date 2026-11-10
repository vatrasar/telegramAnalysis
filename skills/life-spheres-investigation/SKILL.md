---
name: life-spheres-investigation
description: >-
  Investigative probing criteria, forensic diagnostic questions, and bilingual search lexicon
  (Polish FTS5 keywords and English semantic queries) for auditing the 6 foundational life spheres
  (Social Matrix, Work & Ambitions, Worldview & Tech, Family Roots & Domestic Order, Romantic Attachment,
  Leisure & Animals). Use during Phase 4 life spheres audits, behavioral probing, searching for unfulfilled
  ambitions, domestic habits, work ethic, or running targeted queries via query_chat.py.
---

# Life Spheres Investigation & Behavioral Probing Skill

This skill defines the operational workflow, forensic probing criteria, bilingual search vocabulary, and query recipes used to investigate longitudinal chat logs across foundational life spheres and behavioral dimensions.

---

## 1. Overview

Longitudinal chat archives contain rich behavioral evidence, but critical lifestyle indicators (e.g. domestic order, work ethic, unfulfilled ambitions, financial psychology, altruism, relationship with animals) are dispersed across thousands of messages.

This skill equips the agent with:
1. **The 6 Core Life Spheres Probing Framework:** Concrete forensic questions to evaluate real-life behavior.
2. **The Master Bilingual Search Lexicon:** Curated Polish lexical terms for SQLite FTS5 queries (`-s`, `-st`) and English semantic queries for vector search (`--semantic`).
3. **Query Toolchain Recipes:** Concrete CLI commands via `query_chat.py` to retrieve messages, inspect dialogue threads, and trace causal chains.
4. **Evidentiary Protocol:** Principles to distinguish between actual behavioral evidence and unmentioned topics (strict omission vs. evidence synthesis).

---

## 2. When to Use

Activate this skill whenever:
- Auditing the **6 Core Life Spheres** during Phase 4 of an in-depth psychological investigation.
- Searching for specific behavioral indicators, unfulfilled ambitions, work ethic, domestic order, or spending patterns.
- Executing lexical (`-s` / `-st`) or semantic (`--semantic`) searches with `query_chat.py` on `chat.db`.
- Fact-checking or verifying specific lifestyle claims against the chat record.

---

## 3. The 6 Core Life Spheres (Forensic Probing Criteria)

Use these detailed criteria when probing the archive across foundational domains:

### A. Social Matrix & Friendship Dynamics
- **Authentic Friends vs. Superficial Contacts:** Does the subject possess a genuine inner circle of close, trusted confidants, or are social contacts primarily superficial acquaintances, coworkers, or online gaming contacts?
- **Social Cadence & Meeting Frequency:** How often do they actually meet friends offline in real life? Are offline hangouts routine, sporadic, or actively avoided in favor of digital-only exchanges?
- **Shared Social Activities:** How do they spend shared time? (House gatherings, dining/pubs, shared gaming, sports, artistic/intellectual discussions, or mutual venting).
- **Altruism & Helping Others (Prosocial Stance):** Do they genuinely enjoy helping others, offering spontaneous assistance, time, advice, or practical aid? Is their helpfulness selfless and empathic, or transactional (expecting payback), driven by a savior/caretaker complex, or avoided altogether?
- **Friendship Paradigm & Boundaries:** Do they view friends as authentic confidants, an admiring audience, or utilitarian assets? Do they maintain an exclusive inner circle while keeping others at arm's length?
- **Loyalty vs. Door-Slamming:** Do they repair relational fractures, or do they permanently sever ties (*door-slam*) upon the first perceived disloyalty or slight?
- **Envy vs. Compersion & Confidentiality:** How do they react to peers' achievements? Genuine pride vs. passive-aggressive minimization, envy, or anxious comparison. Do they guard secrets faithfully or instrumentalize gossip?

---

### B. Professional Sphere, Work Ethic, Ambitions & Financial Psychology
- **Work Ethic & Diligence (Hard Worker vs. Slacker):** Are they a conscientious grinder/workaholic ("pracuś"), driven by perfectionism and duty, or do they slack off ("obijanie się"), procrastinate, coast, or do the bare minimum?
- **Aspirations, Ambitions & Plan Execution Track Record:**
  - *Declared Ambitions:* What scale of ambition do they articulate (career pivots, startups, creative works, degrees, relocations)?
  - *Follow-Through vs. Phantom Declarations:* Over the longitudinal timeline, do they systematically execute declared plans, hit milestones, and follow through, OR do ambitious declarations evaporate into empty words, perpetual postponement, and wishful thinking?
  - *Specific Unfulfilled Ambitions & Abandoned Goals (The Catalogue of Unrealized Dreams):*
    - Explicitly identify, itemize, and name the **concrete unfulfilled ambitions, abandoned ventures, uncompleted qualifications/degrees, dropped projects, or deferred life paths** revealed across the archive (e.g. *"wanted to launch a startup but never did"*, *"planned to study abroad"*, *"abandoned writing a book/creative work"*, *"dreamed of switching to medicine/IT but stayed in a safe job"*).
    - For each identified unfulfilled ambition, investigate:
      1. What was the exact envisioned ambition and when was it declared?
      2. At what stage did execution stall or derail?
      3. What was the true blocker (e.g. perfectionist paralysis, fear of public failure, lack of financial runway, loss of novelty, partner/parental discouragement)?
      4. Does it linger as an open psychic wound, a chronic source of melancholy/regret ("what could have been"), or was it maturely mourned and replaced?
  - *Coping with Failure:* How do they handle stalled projects or unrealized dreams? Mature self-reflection and realistic recalibration vs. externalized blame (blaming systems, bosses, bad timing) and rationalization.
- **Team Player vs. Lone Wolf:** Are they cooperative and supportive in group endeavors, or individualistic, territorial, or resistant to shared ownership and teamwork?
- **Authority Relations:** Respect for meritocratic leadership vs. knee-jerk defiance, submissiveness, cynical contempt for hierarchy, or impostor syndrome.
- **Financial Psychology & Spending Habits:**
  - *Attitude Toward Money:* Is money viewed as existential safety, scorecard of self-worth, an instrument of autonomy, or an object of chronic anxiety?
  - *Frugality vs. Lavishness / Extravagance (Oszczędność vs. Rozrzutność):* Calculated, restrictive saver vs. impulsive, lavish spender. Do they indulge in higher-end lifestyle spending or show extreme frugality, guilt, or anxiety when spending money?
  - *Appetite for Premium vs. Budget Goods:* Preference for expensive, flagship consumer electronics and branded items (e.g. desire for flagship smartphones, premium gadgets, designer goods) vs. deliberate satisfaction with economical, functional, cheaper alternatives.
  - *Everyday Budgeting & Financial Dynamics:* How do they handle everyday budgeting, luxury purchases, debts, investments, or treating others?

---

### C. Worldview, Politics & Technology Stance
- **Socio-Political Beliefs & Civic Orientation:**
  - *Doctrinal & Partisan Orientation:* Explicit political stance (conservative, liberal, libertarian, left-wing, centrist, or apolitical/disillusioned), stance on governance, civic duties, and societal order.
  - *Sympathies Toward Political Figures & Movements:* Stance toward specific political leaders, candidates, or political movements discussed in the archive (admiration, revulsion, or reflective neutrality).
  - *Civic & Electoral Motivations:* What drives their voting decisions or civic behavior? (Programmatic ideology vs. affective/emotional impulses, e.g. voting out of sympathy or pity vs. civic duty vs. cynical disengagement).
  - *Stance Toward Nations & Nationalities:* Attitudes toward specific countries, foreign cultures, and nationalities (curiosity, warmth, cosmopolitanism vs. prejudice, skepticism, or ethnocentric distance).
  - *Ethical Stance on Discrimination & Racism:* Evaluation of prejudice, discrimination, xenophobia, or racism (does the subject express or tolerate ethnic stereotyping, or actively uphold egalitarianism, fairness, and cultural tolerance?).
  - *Geopolitical & Cultural Alignments:* Positioning regarding international conflicts, cultural sovereignty, and religious/ethnic solidarity.
  - *Boundary Maintenance in Political Debates:* Tolerance when interlocutors express opposing political or ideological views (collaborative pluralism vs. rigid boundary setting, e.g. demanding mutual respect and non-imposition vs. relational rupture).
- **Attitude Toward Artificial Intelligence & Modern Technology:**
  - *AI & Tech Posture:* Are they enthusiastic early adopters, pragmatic utilitarians, philosophical skeptics, or indifferent/uninterested in modern tech trends?
  - *Reaction to Introduced Tools & Innovations:* When an interlocutor recommends or introduces a new digital tool, software, or technology, does the subject show curiosity and try it, or do they simply show a lack of interest, shrug it off, or prefer familiar routines? (Avoid forcing far-fetched psychological diagnoses when a reaction simply reflects standard disinterest in the subject matter).
  - *Practical Digital Tool Usage:* How do they actually utilize digital infrastructure? (Advanced workflows and intellectual exploration vs. purely basic communication, administrative utilities, and low-friction mobile games).
- **Cognitive Style in Debate:** Do they lean on empirical evidence and formal logic, or emotional appeal and moral superiority? Do they respect ideological opponents or dehumanize them?

---

### D. Family Roots, Parental Imprints & Domestic Environment
- **Parental Imprints:** Mother and father archetypes; presence of conditional love, harsh discipline, emotional neglect, or overprotection.
- **Sibling Dynamics & Parentification:** Were they forced to take on adult caretaker roles prematurely?
- **Generational Traps:** Did they witness an entrapped or unhappy parental marriage? How does this dictate their fear of commitment?
- **Approach to Domestic Order & Living Space:**
  - *Orderliness vs. Chaos:* Meticulous cleanliness and structured minimalism vs. high clutter tolerance, disorganization, or chronic mess.
  - *Domestic Environment as Psychological Mirror:* How does their living space reflect their internal state? (E.g. compulsive cleaning as a stress-relief mechanism vs. neglecting environment during depressive/overwhelmed episodes).

---

### E. Romantic Attachment & Relational Patterns
- **Relational History & Archetypes:** Tracing romantic partners, breakups, betrayals, and formative lessons across the timeline.
- **Intimacy Ceilings & Push-Pull Dynamics:** At what point does closeness trigger defensive anxiety or deactivating maneuvers?
- **Conflict Resolution in Romance:** Reconnection and repair attempts vs. emotional stonewalling, scorekeeping, or dramatic exits.

---

### F. Leisure, Sports, Travel, Vacations & Relationship with Animals
- **Free Time & Hobbies (Restoration Modes):** How do they actively choose to spend discretionary time? Passive consumption (scrolling, streaming) vs. active passions (gaming, reading, creative arts, physical sports, technical tinkering, solo contemplation).
- **Sports & Physical Activity:**
  - *Exercise Habits & Preferences:* Do they practice sports or physical training (gym, running, swimming, cycling, team sports, martial arts, fitness classes)? Do they follow/watch sports as a spectator?
  - *Function of Physical Culture:* Is exercise a discipline, a stress-relief mechanism, an aesthetic body-image drive, or do they express active aversion/apathy toward physical exertion (sedentary lifestyle)?
- **Vacation & Holiday Style:** How do they spend vacations and time off?
  - *Style & Structure:* Rigidly planned itineraries vs. spontaneous drifting; resort comfort vs. adventurous exploration; traveling solo vs. with partners/friends.
  - *Psychological Decompression:* Can they genuinely unplug from work and duties, or do they carry anxiety and hyper-vigilance into their time off?
- **Travel Motivations & Modus Operandi:**
  - *Drivers:* Driven by cultural curiosity, escape from routine, wanderlust, romantic getaways, or staying grounded as a committed homebody.
  - *Pattern:* Domestic getaways vs. international travel, high-frequency nomadism vs. rare, carefully curated journeys.
- **Relationship with Animals & Pets:**
  - *Pet Ownership & Affection:* Do they have pets (dogs, cats, etc.), desire pets, or avoid them?
  - *Emotional Bond & Empathy:* How do they interact with and talk about animals? Animal empathy serves as a potent window into their instinctual warmth, capacity for unconditional care, or sensory/cleanliness boundaries.

---

## 4. Query Toolchain Recipes (`query_chat.py`)

All searches operate against the analytical SQLite database (default: `chat.db` in workspace root):

### 4.1 Lexical Keyword Search (`-s` / `-st`)
```bash
# Search individual messages for domestic order keywords:
python3 project/scripts/query_chat.py --db chat.db -s "sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać"

# Search full dialogue threads for work ethic and leadership:
python3 project/scripts/query_chat.py --db chat.db -st "praca OR szef OR nadgodziny OR leniuchować OR obijać OR awans OR lider"

# Scope search to a specific interlocutor / chat:
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" -s "pieniądze OR oszczędzać OR kredyt"
```

### 4.2 Semantic Vector Search (`--semantic`)
```bash
# Probe unfulfilled ambitions and abandoned dreams semantically:
python3 project/scripts/query_chat.py --db chat.db --semantic "unfulfilled ambitions, abandoned dreams, deferred projects, regret"

# Probe attitude toward AI and automation:
python3 project/scripts/query_chat.py --db chat.db --semantic "attitude toward artificial intelligence, automation, machine learning"
```

### 4.3 Context Verification ($N-5 \dots N+5$)
Before adopting any search result as evidence, inspect surrounding context:
```bash
# Inspect the direct causal reply chain:
python3 project/scripts/query_chat.py --db chat.db -c <message_id>

# Inspect full dialogue thread transcript:
python3 project/scripts/query_chat.py --db chat.db -t <thread_id>

# Inspect local context window around a specific message:
python3 project/scripts/query_chat.py --db chat.db -f <message_id> -w 5
```

---

## 5. The Master Bilingual Probing Lexicon

Use this lookup table to target specific lifestyle, relational, and behavioral dimensions:

| Analytical Target | Polish Query Keywords (`-s`, `-st`) | English / Semantic Query Keywords (`--semantic`) | Primary Focus & Diagnostic Questions |
| :--- | :--- | :--- | :--- |
| **Domestic Order & Cleanliness** | `sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać OR myć OR zmywać OR pranie OR czysto OR brudno` | `cleaning OR mess OR clutter OR tidy OR neat OR chores OR clean apartment OR dirty dishes` | Domestic orderliness vs. chaos/mess tolerance; cleaning as stress coping; environment as psychological mirror. |
| **Altruism & Helping Others** | `pomoc OR pomóc OR pomagać OR przysługi OR wsparcie OR poradzić OR wolontariat OR bezinteresownie` | `helping others OR altruism OR favor OR assist OR support OR giving advice OR selfless` | Spontaneous prosocial helpfulness vs. transactional support, savior complex, or boundary avoidance. |
| **Friendship Cadence & Outings** | `spotkanie OR spotkać OR piwo OR kawa OR wyjście OR znajomi OR przyjaciel OR impreza OR domówka` | `meeting friends OR hangout OR coffee OR drinks OR pub OR party OR socializing` | Cadence of offline social meetings; superficial contacts vs. intimate confidants; real-life vs. digital-only interaction. |
| **Work Ethic & Diligence** | `praca OR pracować OR nadgodziny OR zapieprz OR harować OR obowiązki OR sumienny OR deadline OR awans` | `work ethic OR hardworking OR overtime OR diligent OR ambitious OR professional duty` | Conscientious grinder ("pracuś") vs. coasting, slacking ("obijanie"), or minimal viable effort. |
| **Unfulfilled Ambitions & Dropped Goals** | `marzenie OR chciałem OR planowałem OR rzuciłem OR zrezygnowałem OR nie wyszło OR startup OR studia OR żałuję` | `unfulfilled ambition OR abandoned project OR dropped out OR regret OR deferred dream OR failed plan` | Catalogue of unrealized dreams; dropped degrees/startups; open psychic wounds vs. mature mourning and recalibration. |
| **Team Player vs. Lone Wolf** | `zespół OR drużyna OR współpraca OR gracz zespołowy OR razem OR samotnik OR indywidualista` | `teamwork OR team player OR collaboration OR cooperative OR lone wolf` | Cooperative synergy and credit sharing vs. fierce autonomy, silo working, and distrust of collective efforts. |
| **Sports & Physical Activity** | `sport OR siłownia OR bieganie OR biegam OR trening OR ćwiczyć OR rower OR basen OR mecz` | `sports OR gym OR workout OR running OR fitness OR exercise OR training` | Exercise habits and athletic discipline; body image driver vs. sedentary lifestyle and physical apathy. |
| **Leisure & Hobbies** | `czas wolny OR hobby OR grać OR seriale OR czytać OR odpoczynek OR nudzi mi się` | `free time OR hobby OR gaming OR watching OR reading OR bored` | Discretionary restoration modes; passive consumption (scrolling, streaming) vs. active passions (gaming, arts, reading, tinkering). |
| **Political & Societal Views** | `polityka OR wybory OR rząd OR podatki OR partia OR państwo OR wolność` | `politics OR elections OR government OR taxes OR freedom OR laws` | Socio-political orientation; stance on governance, civic duties, liberty, tradition; empirical debate style vs. moral superiority. |
| **Vacations & Holidays** | `urlop OR wakacje OR wyjazd OR odpocząć OR plaża OR hotel OR wolne w pracy` | `vacation OR holiday OR summer trip OR resort OR time off` | Vacation structure (rigid planning vs. spontaneous drifting); psychological ability to unplug vs. persistent hyper-vigilance. |
| **AI & Modern Technology** | `AI OR sztuczna inteligencja OR ChatGPT OR model OR robot OR technologia` | `AI OR artificial intelligence OR LLM OR automation OR tech` | Early adopter vs. skeptic vs. apprehensive; daily practical workflow integration vs. resistance to technological shifts. |
| **Animals & Pets** | `pies OR piesek OR kot OR kotek OR zwierzak OR pupil OR schronisko` | `dog OR puppy OR cat OR kitten OR pet OR animal OR shelter` | Pet ownership; emotional warmth and empathy toward animals; sensory/cleanliness boundaries. |
| **Travel (Motivations & Style)** | `podróż OR zwiedzać OR samolot OR lot OR zagranica OR walizka OR wycieczka` | `travel OR trip OR flight OR abroad OR sight-seeing OR journey` | Motivations (cultural curiosity, routine escape, wanderlust) vs. committed homebody; domestic vs. international travel. |
| **Money Management & Spending** | `pieniądze OR oszczędzać OR wydać OR drogo OR tanio OR kupić OR finanse OR kredyt` | `money OR save OR spend OR budget OR splurge OR frugal OR debt` | Frugal planning and disciplined saving vs. impulsive spending and status buying; money as safety, autonomy, or guilt. |

---

## 6. Probing Workflow & Step-by-Step Procedure

1. **Select Target Dimensions:** Identify which spheres are required for the investigation phase.
2. **Execute Targeted Queries:** Run Polish lexical (`-s` / `-st`) and English semantic (`--semantic`) searches via `query_chat.py`.
3. **Contextual Verification ($N-5 \dots N+5$):** Inspect candidate matches via `-c <id>` or `-f <id> -w 5`. Verify speaker identity and genuine intent (rule out sarcasm, pasted text, and immediate rebuttals).
4. **Apply Evidentiary Inclusion / Omission:** If evidence is found, synthesize with exact quotes and anchors `[#ID | YYYY-MM-DD]`. If completely unmentioned, **omit the dimension entirely**.

---

## 7. Verification Checklist

Before completing an inquiry into lifestyle or behavioral spheres, verify:
- [ ] Were query terms executed in the appropriate language (Polish lexical `-s`/`-st`, English semantic `--semantic`)?
- [ ] Were candidate quotes verified in surrounding context ($N-5 \dots N+5$)?
- [ ] Were speaker identities disambiguated (subject vs. interlocutor vs. quoted text)?
- [ ] Are all reported observations grounded in concrete message IDs (`[#ID | YYYY-MM-DD]`)?
- [ ] Were completely unmentioned life spheres omitted entirely without placeholder boilerplates?
