---
trigger: always_on
---

# Analytical CLI Engine & Database Query Protocol

These rules govern database querying, CLI exploration tools, diagnostic radars, and retrieval capabilities used during conversation analysis.

---

## 1. Zero-Context-Pollution & Database Location Standard

1. **Context Protection Mandate:** NEVER load raw chat files (>1,000 messages) directly into context. All exploration operates via CLI queries against analytical SQLite databases.
2. **Standard Database Location:** Workspace root: `chat.db` (or `data/chat.db`).
3. **One-Off Database Setup:** For initial ingestion (`db_builder.py`), database rebuilding, and vector index generation (`vector_indexer.py --index`), activate the `chat-data-ingestion` skill.

---

## 2. The Primacy of Semantic Vector Search ("Turbo Fajne" & Indispensable)

Dense vector semantic search (`query_chat.py --semantic "<concept>"`) is the **primary, indispensable discovery engine** for psychological, attitudinal, and behavioral inquiry. 

### 2.1 Why Vector Search is Fundamentally Superior to Lexical Keyword Search
1. **The Natural Language Divergence Problem:**
   Human interlocutors in informal messaging **never speak using textbook, clinical, or academic terminology**.
   - **Worldview & Politics:** Nobody writes *"Mój światopogląd to konserwatyzm fiskalny"* or *"Reprezentuję centrolewicę"*. Instead, they vent about municipal tax hikes, argue about voting in local elections, discuss political corruption, criticize state healthcare, complain about border regulations, or share memes about politicians. Lexical search for `-s "polityka OR doktryna"` yields 0 hits or misses 90% of political discussions.
   - **Ways of Saving & Financial Psychology:** Nobody writes *"Stosuję strategię oszczędnościową i wykazuję awersję do ryzyka"*. Instead, they discuss hunting for second-hand electronics on OLX/Allegro, express visceral guilt after eating at an overpriced restaurant, complain about rising rent and inflation, refuse to take bank loans (*"pętla na szyję"*), or brag about fixing an old laptop themselves. Lexical search for `-s "finanse OR oszczędzanie"` misses everyday financial behavioral patterns.
   - **Psychological Defenses & Attachment:** Nobody writes *"Aktywuję styl unikający i deaktywuję bliskość"* or *"Dewaluuję twoje potrzeby"*. When confronted with emotional vulnerability, an avoidant individual abruptly changes the subject to sports, cracks a cynical joke, deflects with work stress, or lapses into a 48-hour silence. Lexical search for `-s "lęk przed bliskością"` yields 0 hits.
2. **Dense Vector Embeddings Map Underlying Intent & Meaning:**
   Semantic embeddings embed entire dialogue thread contexts into high-dimensional semantic space. They capture conceptual proximity, emotional valence, and behavioral stance — **even if not a single search word appears in the literal chat transcript**.
3. **Investigative Division of Labor:**
   - **Lexical FTS5 Search (`-s`):** Reserved strictly for **concrete named entities, specific nouns, and factual biographical anchors** (e.g. pet names, universities, companies, specific city names, model numbers, dates, purchases).
   - **Semantic Vector Search (`--semantic`):** **MANDATORY** for all psychological, philosophical, political, relational, financial, and attitudinal probing. Concluding absence or presence of an attitude without vector search is strictly forbidden.

---

## 3. Daily Driver Analytical CLI Matrix (`query_chat.py`)

Execute all analysis via `python3 project/scripts/query_chat.py --db chat.db`:

### 3.1 Qualitative Search & Context Inspection (Primary Evidence Tools)
```bash
# Semantic Vector Search (MANDATORY for attitudes, psychology, worldview, saving, defenses):
python3 project/scripts/query_chat.py --semantic "political opinions, voting, government policies, civic duty"
python3 project/scripts/query_chat.py --semantic "saving money, frugal habits, buying second-hand, guilt when spending"
python3 project/scripts/query_chat.py --semantic "fear of commitment, deflecting intimacy with humor, emotional avoidance"

# Batch Multi-Concept Semantic Vector Search (Execute multiple concepts in one pass):
python3 project/scripts/query_chat.py \
  --semantic "political opinions and elections" \
  --semantic "attitude towards saving and money management" \
  --semantic "unfulfilled ambitions and career regret"

# Lexical FTS5 Search (Reserved for concrete named entities and biographical nouns):
python3 project/scripts/query_chat.py -s "keyword1 OR keyword2" -s "must_have"
python3 project/scripts/query_chat.py -s "keyword" -S "<SenderName>"
python3 project/scripts/query_chat.py -st "topic keyword"

# Context Verification (Mandatory N-5 ... N+5 Audit):
python3 project/scripts/query_chat.py --around <msg_id> -n 5      # Chronological window across thread lines
python3 project/scripts/query_chat.py -t <thread_id_or_msg_id>    # Full dialogue thread transcript
python3 project/scripts/query_chat.py -c <msg_id>                 # Vertical parent quote & reply tree
python3 project/scripts/query_chat.py -f <msg_id> -n 10 -w 5      # In-thread window with preceding turns

# Dedicated Long Message Inspection (Avoids context truncation):
python3 project/scripts/query_chat.py -m <msg_id> --part 1        # Paginated viewing
python3 project/scripts/query_chat.py -m <msg_id> --all           # Complete uninterrupted text
python3 project/scripts/query_chat.py --stats -s "keyword" --json # Machine-readable JSON output
```

### 3.2 Quantitative Relational Mining & Time Metrics
```bash
# Global baselines & dyadic breakdown:
python3 project/scripts/query_chat.py --stats
python3 project/scripts/query_chat.py -C "<chat_id>" --stats --gaps

# Silence gaps (>= 24h) & initiative tracking (% who broke silence):
python3 project/scripts/query_chat.py --gaps

# Longitudinal density & crisis spike detection:
python3 project/scripts/query_chat.py --timeline
python3 project/scripts/query_chat.py --burning-days
```

### 3.3 Diagnostic Salience Radars (System-1 Triage)
```bash
python3 project/scripts/query_chat.py --anomalies-only   # Interlocutor shock, call-outs, friction
python3 project/scripts/query_chat.py --emotional-peaks  # Intense sadness, joy, rage
python3 project/scripts/query_chat.py --advice-seeking   # Existential dilemmas, intimate confessions
python3 project/scripts/query_chat.py --triaged-threads --limit 25  # Top scored salience threads
python3 project/scripts/query_chat.py --triage-status   # Summary of radar hits
```

### 3.4 Entity Disambiguation & Role Cardinality
```bash
# Inspect registered entities and role descriptors:
python3 project/scripts/query_chat.py -C "<chat_id>" --entities
python3 project/scripts/query_chat.py -C "<chat_id>" --descriptors

# Lazy On-Demand Cardinality Audit (K=1 vs K>=2):
python3 project/scripts/query_chat.py -C "<chat_id>" --audit-descriptor "<role_or_descriptor>"

# Register verified third-party entity:
python3 project/scripts/query_chat.py -C "<chat_id>" --register-entity "<Name>" --role "<Role>" --desc "<Notes>"
```

### 3.5 Investigation Checklists & Progress Gates
```bash
# Life Spheres Status (tracks resolution progress and semantic vector probe coverage):
python3 project/scripts/query_chat.py -C "<chat_id>" --checklist
python3 project/scripts/checklist.py -C "<chat_id>" --status

# Thread Forensic Checklist (Next pending thread to audit):
python3 project/scripts/query_chat.py -C "<chat_id>" --next-thread
python3 project/scripts/thread_checklist.py -C "<chat_id>" --status
```

---

## 4. Per-Message Context Protection Guard

- All CLI display functions enforce a per-message truncation limit of **1,500 characters**.
- Messages exceeding 1,500 characters display a truncation notice:
  `[⚠️ WIADOMOŚĆ UCIĘTA: Wyświetlono 1497 z 3059 znaków (Część 1/3)]`
- To safely inspect long messages without context pollution, execute:
  `python3 project/scripts/query_chat.py -m <msg_id> --part <N>` (or `--all`).
