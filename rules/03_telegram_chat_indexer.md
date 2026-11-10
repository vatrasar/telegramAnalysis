---
trigger: always_on
---

# Analytical CLI Engine & Database Query Protocol

These rules govern database querying, CLI exploration tools, diagnostic radars, and retrieval capabilities used during conversation analysis.

---

## 1. Zero-Context-Pollution & Database Location Standard

1. **Context Protection Mandate:**
   - **NEVER load raw chat logs (>1,000 messages) directly into the agent context.** All exploration, fact-checking, and psychological analysis operate via CLI queries against analytical SQLite databases.
2. **Standard Database Location:**
   - The primary analytical database lives in the workspace root: `chat.db` (or `data/chat.db`).

---

## 2. Master Analytical CLI Capabilities Matrix (`query_chat.py`)

The agent interacts with the analytical database via `project/scripts/query_chat.py` (or `.agents/scripts/query_chat.py`). Use these diagnostic flags to mine evidence:

### 2.1 Diagnostic Radars & Triage Hunters (System-1 Screened Salience)
Scan pre-filtered psychological high-salience moments without manual keyword guessing:
```bash
# Radar 1: Behavioral anomalies & interlocutor shock (unusual reactions, call-outs)
python3 project/scripts/query_chat.py --db chat.db --anomalies-only

# Radar 2: Acute emotional peaks (profound sadness, euphoric joy, intense rage)
python3 project/scripts/query_chat.py --db chat.db --emotional-peaks

# Radar 3: Advice-seeking dilemmas & intimate disclosures (existential life questions)
python3 project/scripts/query_chat.py --db chat.db --advice-seeking

# Priority ranking: Top triaged threads sorted by salience score (0–100)
python3 project/scripts/query_chat.py --db chat.db --triaged-threads --limit 25

# Triage system status and radar hit summary
python3 project/scripts/query_chat.py --db chat.db --triage-status
```

---

### 2.2 Quantitative Relational Mining & Time Metrics
Extract empirical baselines, attachment initiative balances, and crisis periods:
```bash
# Global overview: message volume, word counts, per-chat shares, active dates
python3 project/scripts/query_chat.py --db chat.db --stats

# Silence analysis: gaps >= 24h, duration, who broke the silence (initiative %)
python3 project/scripts/query_chat.py --db chat.db --gaps

# Longitudinal density: monthly message counts to track relationship trajectory
python3 project/scripts/query_chat.py --db chat.db --timeline

# Anomaly detection: days with statistically extreme message volume (crisis spikes)
python3 project/scripts/query_chat.py --db chat.db --burning-days

# Dyadic focus: isolate all metrics to a specific contact / interlocutor
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" --stats --gaps
```

---

### 2.3 Qualitative Retrieval, Semantic Search & Context Window Inspection
Retrieve specific verbatim evidence, inspect single messages, and perform mandatory context audits:
```bash
# FTS5 Lexical Search: multi-keyword boolean search on messages
python3 project/scripts/query_chat.py --db chat.db -s "przepraszam OR wybacz" -s "wina"

# Filter Lexical Search by Sender:
python3 project/scripts/query_chat.py --db chat.db -s "work" -S "Ismi"

# Dedicated Single Message Inspection with Pagination:
python3 project/scripts/query_chat.py --db chat.db -m <msg_id> --part 1
python3 project/scripts/query_chat.py --db chat.db -m <msg_id> --part 2
# Full message display without pagination:
python3 project/scripts/query_chat.py --db chat.db -m <msg_id> --all

# FTS5 Thread Search: search reconstructed dialogue threads by topic
python3 project/scripts/query_chat.py --db chat.db -st "kredyt OR mieszkanie OR kupno"

# Semantic Vector Search: retrieve threads by psychological concept / abstract behavior
python3 project/scripts/query_chat.py --db chat.db --semantic "fear of vulnerability and emotional avoidance"

# Full Thread Transcript (with parent & child lineage headers):
python3 project/scripts/query_chat.py --db chat.db -t <thread_id_or_msg_id>

# Vertical Causal Quote Chain: trace exact parent quotes and replies (N-5 ... N+5)
python3 project/scripts/query_chat.py --db chat.db -c <msg_id>

# Local Context Window: display N messages surrounding target message within the same thread
python3 project/scripts/query_chat.py --db chat.db -f <msg_id> -n 10 -w 5

# Horizontal Chronological Audit Window (N-5 ... N+5 across thread boundaries):
python3 project/scripts/query_chat.py --db chat.db --around <msg_id> -n 5

# Machine-Readable JSON: emit structured JSON output for agent parsing
python3 project/scripts/query_chat.py --db chat.db --stats -s "awans" --json
```

#### 2.3.1 Per-Message Context Protection Guard
- All print functions (`print_search_messages`, `print_chronological_around`, `print_thread`, `print_thread_slice`, `print_quote_chain`) enforce a **per-message character limit** (default: 1500 chars).
- Normal conversational turns (short dialog flow) are displayed completely without artificial cumulative caps.
- When an individual message exceeds 1500 chars (long pasted articles, forwarded messages, or partners' essays), it is cleanly truncated on a word boundary, followed by an explicit notice:
  ```text
  ... [⚠️ WIADOMOŚĆ UCIĘTA: Wyświetlono 1497 z 3059 znaków (Część 1/3).
      Aby przeczytać pełną treść lub kolejne części, użyj:
      python3 project/scripts/query_chat.py -m <msg_id> --part 2 (lub --all)]
  ```
- To read the full text safely without flooding the context window, use `-m <msg_id> --part <N>` or `--all`.

---

### 2.4 Entity Disambiguation, Role Cardinality & Watchdog Verification
Inspect and manage third-party entities and scoped role descriptors:
```bash
# Display registered third-party entities for a specific conversation
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" --entities

# Display registered role descriptors and their cardinality (K=1 vs K>1)
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" --descriptors

# Perform Lazy On-Demand Cardinality Audit on a newly encountered role or descriptor
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" --audit-descriptor "sister"

# Register or update a verified third-party entity under chat scope
python3 project/scripts/query_chat.py --db chat.db -C "<chat_id_or_name>" --register-entity "Dustin" --role "Chat friend from Oregon" --desc "pothead, mushroom farmer" --non-romantic

# Execute System-1 Watchdog Double-Check on a thread to detect overlooked entities
python3 project/scripts/query_chat.py --db chat.db --watchdog-check <thread_id> --known "Dustin"
```

---

## 3. Mandatory Chat Data Ingestion Skill Activation Gate

To preserve system context, data engineering pipelines, database parsing tools, vectorization scripts, and SQLite schemas are maintained in a specialized skill:

> [!IMPORTANT]
> **Activation Requirement:**
> When ingesting raw chat exports (`rozmowy/*.json`), running clean database rebuilds, generating vector embeddings, executing `triage_threads.py`, or writing custom direct SQL queries, the agent **MUST activate the `chat-data-ingestion` skill**.
>
> The skill provides:
> - Pre-flight environment check (`setup_config.py`).
> - Database generation and incremental refresh (`db_builder.py`).
> - Dense vector generation (`vector_indexer.py --index`).
> - Thread disentanglement algorithm mechanics (RAT-FBP).
> - Full SQLite database schema reference (`chats`, `messages`, `threads`, `silence_gaps`, `thread_triage`).
