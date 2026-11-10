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

## 2. Daily Driver Analytical CLI Matrix (`query_chat.py`)

Execute all analysis via `python3 project/scripts/query_chat.py --db chat.db`:

### 2.1 Qualitative Search & Context Inspection (Primary Evidence Tools)
```bash
# Lexical FTS5 Search (messages):
python3 project/scripts/query_chat.py -s "keyword1 OR keyword2" -s "must_have"
python3 project/scripts/query_chat.py -s "keyword" -S "<SenderName>"

# Thread FTS5 Search & Semantic Vector Search:
python3 project/scripts/query_chat.py -st "topic keyword"
python3 project/scripts/query_chat.py --semantic "fear of vulnerability and emotional avoidance"

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

### 2.2 Quantitative Relational Mining & Time Metrics
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

### 2.3 Diagnostic Salience Radars (System-1 Triage)
```bash
python3 project/scripts/query_chat.py --anomalies-only   # Interlocutor shock, call-outs, friction
python3 project/scripts/query_chat.py --emotional-peaks  # Intense sadness, joy, rage
python3 project/scripts/query_chat.py --advice-seeking   # Existential dilemmas, intimate confessions
python3 project/scripts/query_chat.py --triaged-threads --limit 25  # Top scored salience threads
python3 project/scripts/query_chat.py --triage-status   # Summary of radar hits
```

### 2.4 Entity Disambiguation & Role Cardinality
```bash
# Inspect registered entities and role descriptors:
python3 project/scripts/query_chat.py -C "<chat_id>" --entities
python3 project/scripts/query_chat.py -C "<chat_id>" --descriptors

# Lazy On-Demand Cardinality Audit (K=1 vs K>=2):
python3 project/scripts/query_chat.py -C "<chat_id>" --audit-descriptor "<role_or_descriptor>"

# Register verified third-party entity:
python3 project/scripts/query_chat.py -C "<chat_id>" --register-entity "<Name>" --role "<Role>" --desc "<Notes>"
```

### 2.5 Investigation Checklists & Progress Gates
```bash
# Life Spheres Status:
python3 project/scripts/query_chat.py -C "<chat_id>" --checklist
python3 project/scripts/checklist.py -C "<chat_id>" --status

# Thread Forensic Checklist (Next pending thread to audit):
python3 project/scripts/query_chat.py -C "<chat_id>" --next-thread
python3 project/scripts/thread_checklist.py -C "<chat_id>" --status
```

---

## 3. Per-Message Context Protection Guard

- All CLI display functions enforce a per-message truncation limit of **1,500 characters**.
- Messages exceeding 1,500 characters display a truncation notice:
  `[⚠️ WIADOMOŚĆ UCIĘTA: Wyświetlono 1497 z 3059 znaków (Część 1/3)]`
- To safely inspect long messages without context pollution, execute:
  `python3 project/scripts/query_chat.py -m <msg_id> --part <N>` (or `--all`).
