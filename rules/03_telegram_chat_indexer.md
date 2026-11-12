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

## 2. Qualitative Retrieval: Semantic Vector Search vs. Lexical FTS5

- **Semantic Vector Search (`--semantic`):** **MANDATORY primary discovery engine** for all psychological, political, financial (saving habits, frugality), relational, and attitudinal probing. Chat participants never use clinical or academic terminology (e.g. they discuss road taxes, inflation, or OLX bargains, not "political doctrine" or "frugality strategy"). Vector embeddings capture underlying intent, emotional tone, and behavioral posture regardless of exact phrasing.
- **Lexical FTS5 Search (`-s` / `-st`):** Reserved strictly for **concrete named entities and biographical trivia** (names of people, employers, universities, cities, specific devices, dates).
- **Batch Multi-Concept Search:** Probe multiple concepts in a single CLI call:
  ```bash
  python3 project/scripts/query_chat.py \
    --semantic "political opinions, voting, taxes, government policies" \
    --semantic "saving money, frugal habits, buying second-hand, guilt when spending" \
    --semantic "fear of commitment, deflecting intimacy with humor, emotional avoidance"
  ```

---

## 3. Daily Driver Analytical CLI Matrix (`query_chat.py`)

Execute all analysis via `python3 project/scripts/query_chat.py --db chat.db`:

### 3.1 Qualitative Search & Context Inspection (Primary Evidence Tools)
```bash
# Semantic Vector Search (MANDATORY for attitudes, psychology, worldview, saving, defenses):
python3 project/scripts/query_chat.py --semantic "political opinions, voting, government policies, civic duty"
python3 project/scripts/query_chat.py --semantic "saving money, frugal habits, buying second-hand, guilt when spending"
python3 project/scripts/query_chat.py --semantic "fear of commitment, deflecting intimacy with humor, emotional avoidance"

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

# Silence gaps & tiered initiative tracking (1-3d, 3-7d, 1-2w, 2-4w, 1-3m, >3m):
python3 project/scripts/query_chat.py --gaps
python3 project/scripts/query_chat.py -C "<chat_id>" --gaps
# Filter for prolonged silence gaps (e.g. >= 7 days or >= 30 days):
python3 project/scripts/query_chat.py -C "<chat_id>" --gaps --min-days 7
python3 project/scripts/query_chat.py -C "<chat_id>" --gaps --min-days 30

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
