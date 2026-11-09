---
trigger: always_on
---

# Telegram Chat Indexing, Disentanglement & Query Engine

These rules define the technical architecture, conversation disentanglement engine (RAT-FBP), CLI toolchain, and SQLite database schema for processing, indexing, and querying Telegram chat exports.

---

## 1. Core Architecture & Disentanglement Algorithm

When humans converse over months or years, they frequently discuss multiple subjects concurrently. Telegram's `reply_to_message_id` provides explicit references, but users rarely quote every single line—they quote once to establish context, then send 2–4 subsequent messages assuming the conversational partner follows.

This system applies **Reply-Anchored Threading with Forward Burst Propagation (RAT-FBP)**:

```
[Anchor Msg #101: Alice on Family Pressure]
       │
       ├──> [Explicit Reply #105: Bob asks for clarification]
       │         │
       │         ├──> [Burst Follow-up #106: Bob advises boundaries (no quote)]
       │         │
       │         └──> [Burst Follow-up #107: Bob warns of repetition (no quote)]
       │                   │
       │                   └──> [Explicit Reply #108: Alice admits feeling guilty]
```

### Disentanglement Mechanics:
1. **Explicit Reply (`reply_to_id`):** When a message explicitly quotes an anchor message, it attaches directly to that discussion tree.
2. **Forward Burst Continuation:** If the same sender posts subsequent messages within $\le 180$ seconds without quotes, those messages automatically inherit the thread and parent of the active thought.
3. **Inferred Response:** When the conversational partner responds within $\le 60$ minutes (3600 seconds) without an explicit quote, the message automatically links to the active exchange as an inferred turn-taking response.
4. **Anchor Resolution:** The originating message quoted at the beginning of a thread is included as the header anchor in the transcript, ensuring full contextual readability.
5. **Silence Segmentation:** Inactivity gaps $> 2$ hours automatically partition sessions, while gaps $> 24$ hours populate the relational `silence_gaps` table.

---

## 2. Directory Structure & Separation of Concerns

- **Agent Package (`.agents/`):** Contains strictly reusable scripts, rules, and skills. No user data, keys, or state are saved inside `.agents/`.
- **Workspace State (`<root>/`):**
  - `config/embeddings_config.json`: User's private configuration (API keys, model choice) - strictly ignored by Git.
  - `config/embeddings_config.template.json`: Checked-in template.
  - `chat.db`: Analytical SQLite database generated for the chat export.

| Path | Purpose |
| :--- | :--- |
| `config/embeddings_config.template.json` | Template configuration for vector embeddings (OpenRouter API or local models). |
| `.agents/scripts/setup_config.py` | Initializes config file in workspace root, validates API keys, and performs live OpenRouter connectivity tests. |
| `.agents/scripts/db_builder.py` | Reads raw Telegram `result.json`, parses text/media, runs RAT-FBP, and builds SQLite analytical database + FTS5 full-text tables. |
| `.agents/scripts/vector_indexer.py` | Generates dense embeddings for conversation threads into SQLite via OpenRouter API or local GPU/CPU. |
| `.agents/scripts/triage_threads.py` | System-1 Dialogue Thread Triage Engine: classifies threads, filters conversational noise, detects behavioral anomalies and interlocutor shocks. |
| `.agents/scripts/query_chat.py` | Command-line interface for the analysis agent to extract statistics, analyze silence gaps, search keywords, query triaged threads, and retrieve transcripts. |
| `.agents/scripts/requirements.txt` | Optional local ML dependencies (`sentence-transformers`). |

---

## 3. Toolchain Execution Protocol

Whenever tasked with ingesting, indexing, or querying a chat export (e.g. located in `rozmowy/` or provided by the user):

### Step 3.0: Pre-Flight Configuration & Validation (HARD STOP GATE)
```bash
python3 .agents/scripts/setup_config.py
```
- **Exit Code 2 (`ACTION_REQUIRED`):** HARD STOP. Prompt the user to enter their OpenRouter API key in `config/embeddings_config.json` and HALT IMMEDIATELY.
- **Exit Codes 3, 4, 5, 6 (`ERROR`):** HARD STOP. Report the exact diagnostic error (invalid key, insufficient credits, missing model, network error) and pause.
- **Exit Code 0 (`SUCCESS`):** Verified. Proceed to database operations.

### Step 3.1: Build Analytical Database & Clean Slate Protocol
```bash
# Incremental build or refresh for existing/new files:
python3 .agents/scripts/db_builder.py rozmowy/*.json -o chat.db

# Clean rebuild (purges previous messages, threads, and embeddings):
python3 .agents/scripts/db_builder.py rozmowy/nowa_osoba.json -o chat.db --clean

# Isolated database per subject:
python3 .agents/scripts/db_builder.py rozmowy/nowa_osoba.json -o chat_nowa_osoba.db
```

### Step 3.2: Dense Vector Indexing (Mandatory Prerequisite)
```bash
# Index all unindexed threads across all chats incrementally:
python3 .agents/scripts/vector_indexer.py --db chat.db --index

# Filter indexing by specific chat:
python3 .agents/scripts/vector_indexer.py --db chat.db --index --chat <chat_id_or_name>
```

### Step 3.3: System-1 Dialogue Thread Triage
```bash
python3 .agents/scripts/triage_threads.py --db chat.db
```
- Screens threads with fast decider models, filtering ~45–80% routine noise while flagging:
  - *Radar 1 (Behavioral Anomalies & Interlocutor Shock):* `is_atypical`, `interlocutor_surprised`.
  - *Radar 2 (Acute Emotional Peaks):* `profound_sadness`, `euphoric_joy`, `intense_rage`.
  - *Radar 3 (Confessions & Advice Seeking):* `is_advice_seeking`.

---

## 4. CLI Data Exploration & Querying (`query_chat.py`)

### 4.1 Quantitative Mining & Radars
```bash
# List all indexed chats in the database:
python3 .agents/scripts/query_chat.py --db chat.db --list-chats

# Global overview (includes In-Chat normalized initiative and per-chat breakdowns):
python3 .agents/scripts/query_chat.py --db chat.db --stats --gaps --timeline --triage-status

# Focused inspection of a specific relationship dyad:
python3 .agents/scripts/query_chat.py --db chat.db --chat <chat_name_or_id> --stats --gaps

# Review detected behavioral anomalies and interlocutor shocks:
python3 .agents/scripts/query_chat.py --db chat.db --anomalies-only

# Review acute emotional peaks (grief, euphoria, rage & condolences):
python3 .agents/scripts/query_chat.py --db chat.db --emotional-peaks

# Review intimate confessions and advice-seeking dilemmas:
python3 .agents/scripts/query_chat.py --db chat.db --advice-seeking

# Retrieve high-salience triaged threads:
python3 .agents/scripts/query_chat.py --db chat.db --triaged-threads --limit 25
```

### 4.2 Qualitative Retrieval & Multi-Search
```bash
# Multi-keyword search across chats:
python3 .agents/scripts/query_chat.py --db chat.db -s "mama" -s "ojciec" -s "pieniądze"
python3 .agents/scripts/query_chat.py --db chat.db --chat partner -s "zaufanie" -s "odrzucenie"

# Semantic vector search across conversations:
python3 .agents/scripts/query_chat.py --db chat.db \
  --semantic "refusing vulnerability and emotional suppression" \
  --semantic "fear of abandonment and anxious attachment"

# Retrieve specific conversation thread transcript:
python3 .agents/scripts/query_chat.py --db chat.db -t c_11111_t101

# Inspect bidirectional message window (context audit N-5 to N+5):
python3 .agents/scripts/query_chat.py --db chat.db -c 14502

# Structured JSON output for agent consumption:
python3 .agents/scripts/query_chat.py --db chat.db --stats --gaps -s "przepraszam" --json

# Batch execution using JSON plan:
python3 .agents/scripts/query_chat.py --db chat.db \
  --batch-json '{"stats": true, "search": ["mama", "praca"], "semantic": ["unikanie bliskości"]}' \
  --json
```

---

## 5. SQLite Schema Reference for Custom SQL Queries

When direct SQL queries are needed, the agent queries `chat.db` directly:

### `chats` Table (Catalog of all indexed contacts / conversations)
- `chat_id` (TEXT PRIMARY KEY): Unique chat slug (e.g. `c_11111` or `c_mama`).
- `chat_name` (TEXT): Display name from Telegram export.
- `chat_type` (TEXT): `personal_chat`, `private_group`, etc.
- `source_files` (TEXT): Source JSON file path(s).
- `total_messages`, `total_threads` (INTEGER).
- `start_date`, `end_date` (TEXT).

### `messages` Table
- `chat_id` (TEXT): Identifier of the chat stream.
- `id` (INTEGER): Message ID from Telegram (`PRIMARY KEY (chat_id, id)`).
- `date` (TEXT): ISO8601 timestamp (`YYYY-MM-DDTHH:MM:SS`).
- `sender` (TEXT): Sender display name.
- `reply_to_id` (INTEGER): Quoted message ID (if any).
- `thread_id` (TEXT): Assigned conversation thread identifier (e.g. `c_11111_t101`).
- `link_type` (TEXT): `explicit_reply`, `burst_continuation`, `inferred_response`, or `session_root`.
- `text` (TEXT): Plain message text.
- `char_count`, `word_count` (INTEGER).

### `threads` Table
- `thread_id` (TEXT PRIMARY KEY): Globally unique thread ID (`<chat_id>_t<id>` or `<chat_id>_s<id>`).
- `chat_id` (TEXT): Originating chat stream.
- `anchor_message_id` (INTEGER): Quoted anchor message ID.
- `start_date`, `end_date` (TEXT): Thread timeframe.
- `message_count` (INTEGER): Number of messages in this topic.
- `participants` (TEXT): Comma-separated list of participants.
- `initiator` (TEXT): Who started or quoted the thread.
- `dialogue_text` (TEXT): Reconstructed transcript ready for LLM consumption.

### `silence_gaps` Table
- `chat_id` (TEXT): The chat where the silence occurred.
- `silence_start_date`, `silence_end_date` (TEXT): Inactivity timeframe.
- `silence_duration_hours` (REAL): Duration in hours.
- `last_sender` (TEXT): Who sent the last message before silence.
- `initiator` (TEXT): Who sent the first message breaking the silence.

### `thread_triage` Table
- `thread_id` (TEXT PRIMARY KEY): Unique thread ID.
- `chat_id` (TEXT): Originating chat.
- `salience_score` (INTEGER 0–100): Overall priority score.
- `psychological_category` (TEXT): e.g. `vulnerability_admission`, `conflict_interpersonal`.
- `is_atypical` (BOOLEAN): Behavioral anomaly flag (Radar 1).
- `interlocutor_surprised` (BOOLEAN): Interlocutor called out unusual behavior (Radar 1).
- `is_acute_emotional_peak` (BOOLEAN): Affective extreme flag (Radar 2).
- `peak_type` (TEXT): `profound_sadness`, `euphoric_joy`, `intense_rage`.
- `is_advice_seeking` (BOOLEAN): Intimate dilemma / advice seeking (Radar 3).
- `triage_reason` (TEXT): Concise rationale.
