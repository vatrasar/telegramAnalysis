---
name: targeted-search-lexicon
description: >-
  Provides a comprehensive bilingual search lexicon (Polish lexical keywords and English semantic queries)
  and operational recipes for probing chat archives across foundational life spheres (domestic habits,
  work ethic, unfulfilled ambitions, social matrix, finances, politics, travel, hobbies, AI stance, etc.).
  Use when conducting targeted evidence mining, behavioral probing, or executing keyword and semantic searches via query_chat.py.
---

# Targeted Search Lexicon & Behavioral Probing Skill

This skill defines the operational workflow, bilingual search vocabulary, and query recipes used to probe longitudinal chat logs for practical behavioral dimensions, lifestyle habits, and core life spheres.

---

## 1. Overview

Longitudinal chat archives contain rich behavioral evidence, but critical lifestyle indicators (e.g., domestic order, unfulfilled ambitions, financial habits, altruism) are frequently dispersed across thousands of messages.

This skill equips the agent with:
1. **Bilingual Search Lexicon:** Curated Polish lexical terms for SQLite FTS5 full-text queries (`-s`, `-st`) and English semantic queries for vector search (`--semantic`).
2. **Query Toolchain Recipes:** Concrete CLI commands via `query_chat.py` to retrieve messages, inspect dialogue threads, and trace causal chains.
3. **Evidentiary Protocol:** Principles to distinguish between actual behavioral evidence and unmentioned topics (strict omission vs. evidence synthesis).

---

## 2. When to Use

Activate this skill whenever:
- Auditing the **6 Core Life Spheres** (Social Matrix, Work/Ambition, Worldview/Tech, Family/Domestic, Romance, Leisure/Animals) during Phase 4 of an investigation.
- Searching for specific behavioral indicators, unfulfilled ambitions, work ethic, domestic order, or spending patterns.
- Executing lexical (`-s` / `-st`) or semantic (`--semantic`) searches with `query_chat.py` on `chat.db`.
- Fact-checking or verifying specific lifestyle claims against the chat record.

---

## 3. Query Toolchain Recipes (`query_chat.py`)

All searches operate against the analytical SQLite database (default: `chat.db` in workspace root). Always use `.agents/scripts/query_chat.py` (or `project/scripts/query_chat.py` during development):

### 3.1 Lexical Keyword Search (`-s` / `-st`)
Search individual messages or full threads using SQLite FTS5 syntax (`OR`, `AND`, prefix wildcards `*`):

```bash
# Search individual messages for domestic order keywords
python3 .agents/scripts/query_chat.py --db chat.db -s "sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać"

# Search full dialogue threads for work ethic and leadership
python3 .agents/scripts/query_chat.py --db chat.db -st "praca OR szef OR nadgodziny OR leniuchować OR obijać OR awans OR lider"

# Scope search to a specific interlocutor / chat
python3 .agents/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" -s "pieniądze OR oszczędzać OR kredyt"
```

### 3.2 Semantic Vector Search (`--semantic`)
Search dialogue threads by psychological concept or abstract behavior when lexical terms miss paraphrased expressions:

```bash
# Probe unfulfilled ambitions and abandoned dreams semantically
python3 .agents/scripts/query_chat.py --db chat.db --semantic "unfulfilled ambitions, abandoned dreams, deferred projects, regret"

# Probe attitude toward AI and automation
python3 .agents/scripts/query_chat.py --db chat.db --semantic "attitude toward artificial intelligence, automation, machine learning"
```

### 3.3 Dual-Pronged Hybrid Search (Lexical + Semantic)
Combine lexical keyword constraints with semantic vector ranking for maximum precision:

```bash
python3 .agents/scripts/query_chat.py --db chat.db \
  -s "planuję OR plany OR marzenie OR projekt" \
  --semantic "long-term aspirations and milestone execution"
```

### 3.4 Context Verification ($N-5 \dots N+5$)
Before adopting any quote or search result as analytical evidence, inspect its surrounding context:

```bash
# Inspect the direct causal reply chain
python3 .agents/scripts/query_chat.py --db chat.db -c <message_id>

# Inspect full dialogue thread transcript
python3 .agents/scripts/query_chat.py --db chat.db -t <thread_id>

# Inspect local context window around a specific message
python3 .agents/scripts/query_chat.py --db chat.db -f <message_id> -w 5
```

---

## 4. The Master Bilingual Probing Lexicon

Use this lookup table to target specific lifestyle, relational, and behavioral dimensions:

| Analytical Target | Polish Query Keywords (`-s`, `-st`) | English / Semantic Query Keywords (`--semantic`) | Primary Focus & Diagnostic Questions |
| :--- | :--- | :--- | :--- |
| **Domestic Order & Cleanliness** | `sprzątanie OR bałagan OR porządek OR syf OR kurz OR sprzątać` | `cleaning OR mess OR tidy OR clutter OR chore OR apartment` | Orderliness vs. chaos; living space as a psychological mirror; cleaning as stress relief vs. neglect during depression. |
| **Friends, Social Cadence & Meetups** | `znajomi OR przyjaciel OR kumpel OR wyjście OR piwo OR spotkać OR na żywo` | `friends OR hang out OR meet up OR drinking OR socializing` | Authentic confidants vs. superficial acquaintances; cadence of offline real-world meetings vs. digital-only exchanges. |
| **Altruism & Helping Others** | `pomóc OR pomoc OR pomagam OR przysługa OR wsparcie OR poradzić OR wyręczyć` | `help OR helping OR favor OR support OR altruism OR assist OR volunteer` | Spontaneous, empathetic assistance vs. transactional payback; savior/caretaker dynamic vs. indifference. |
| **Work Ethic & Team Role** | `praca OR szef OR nadgodziny OR leniuchować OR obijać OR awans OR lider OR polecenia` | `work ethic OR boss OR overtime OR slacking OR leader OR task` | Conscientious grinder/workaholic vs. slacker/procrastinator; leadership and taking initiative vs. passive task executor. |
| **Aspirations & Plan Execution** | `planuję OR plany OR cel OR marzenie OR ambicja OR projekt OR zamierzam OR postanowiłem OR zrealizować OR rzucić` | `plan OR goal OR ambition OR project OR intention OR execute OR follow through OR milestone` | Scale of articulated ambitions; longitudinal follow-through vs. phantom declarations and perpetual postponement. |
| **Unfulfilled Ambitions & Abandoned Plans** | `chciałem być OR marzyłem o OR miałem plan OR zrezygnowałem OR nie wyszło OR odpuściłem OR żałuję OR rzuciłem OR niedokończone OR planowałem` | `used to want OR dreamed of OR had a plan OR gave up OR didn't work out OR dropped out OR regret OR abandoned OR unfinished` | Catalogue of unrealized dreams; dropped degrees/startups; open psychic wounds vs. mature mourning and recalibration. |
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

## 5. Probing Workflow & Step-by-Step Procedure

When conducting an inquiry into life spheres and behavioral dimensions, follow this systematic procedure:

1. **Select Target Dimensions:**
   Identify which spheres from the inquiry guide are relevant to the user request or required for comprehensive profiling.

2. **Execute Targeted Queries:**
   - Run lexical searches using the exact Polish query strings from Section 4.
   - If the archive has vector indexing enabled (`vector_indexer.py`), run complementary `--semantic` queries.
   - Limit initial retrieval to substantive samples (`--limit 15`).

3. **Contextual Verification ($N-5 \dots N+5$):**
   - For any message matching key themes, run `--chain` (`-c <id>`) or `--window` (`-f <id> -w 5`).
   - Check speaker attribution (distinguish subject declarations from quotes, interlocutor statements, or sarcasm).

4. **Apply the Evidentiary Inclusion / Omission Protocol:**
   - **Evidence Found:** If substantive evidence emerges, synthesize the finding into the research scratchpad (`evidence_ledger.md`) with concrete quotes and dates.
   - **Zero Evidence Found:** If the topic was never discussed across the entire longitudinal archive, **completely omit the sub-dimension**. NEVER generate negative placeholder disclaimers (e.g. *"Brak informacji o sporcie"*).

---

## 6. Verification Checklist

Before completing an inquiry into lifestyle or behavioral spheres, verify:
- [ ] Were query terms executed in the appropriate language (Polish lexical `-s`/`-st`, English semantic `--semantic`)?
- [ ] Were all candidate quotes verified with surrounding context ($N-5 \dots N+5$)?
- [ ] Were speaker identities disambiguated (subject vs. interlocutor vs. quoted text)?
- [ ] Are all reported observations grounded in concrete message IDs (`[#ID | YYYY-MM-DD]`)?
- [ ] Were completely unmentioned life spheres omitted entirely without placeholder boilerplates?
