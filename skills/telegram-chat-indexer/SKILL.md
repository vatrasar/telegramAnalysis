---
name: telegram-chat-indexer
description: >-
  Preprocesses, disentangles, and indexes massive Telegram chat exports (50,000+ messages)
  into an analytical SQLite database and vector index. Reconstructs multi-topic interleaved conversations,
  resolves quote trees and burst follow-ups without quotes, computes silence/gap dynamics,
  and provides CLI tools for quantitative and qualitative psychological profiling.
---

# Telegram Chat Indexer & Thread Disentangler

This skill equips an AI analysis agent to process, structure, and query massive raw Telegram chat logs (e.g., 40,000–50,000+ messages) without saturating the LLM context window.

It solves the core challenge of **interleaved multi-topic conversations** where participants juggle 20–50 parallel topics using Telegram quotes, accompanied by unquoted follow-up bursts.

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

### The Disentanglement Rules:
1. **Explicit Reply (`reply_to_id`):** When a message explicitly quotes an anchor message, it attaches directly to that discussion tree.
2. **Forward Burst Continuation:** If the same sender posts subsequent messages within $\le 180$ seconds without quotes, those messages automatically inherit the thread and parent of the active thought.
3. **Inferred Response:** When the conversational partner responds within $\le 60$ minutes (3600 seconds) without explicit quote, the message automatically links to the active exchange as an inferred turn-taking response.
4. **Anchor Resolution:** The originating message quoted at the beginning of a thread is included as the header anchor in the transcript, ensuring full contextual readability.
5. **Silence Segmentation:** Inactivity gaps $> 2$ hours automatically partition sessions, while gaps $> 24$ hours populate the relational `silence_gaps` table.

---

## 2. Directory Structure & Separation of Concerns

- **Agent Package (`project/`):** Contains strictly reusable scripts, rules, and skills. No user data, keys, or state are saved inside `project/`.
- **Workspace State (`<root>/`):**
  - `config/embeddings_config.json`: User's private configuration (API keys, model choice) - strictly ignored by Git.
  - `config/embeddings_config.template.json`: Checked-in template.
  - `chat.db`: Analytical SQLite database generated for the chat export.

| Path | Purpose |
| :--- | :--- |
| `config/embeddings_config.template.json` | Template configuration for vector embeddings (OpenRouter API or local models). |
| `project/scripts/setup_config.py` | Initializes config file in workspace root, validates API keys, and performs live OpenRouter connectivity tests. |
| `project/scripts/db_builder.py` | Reads raw Telegram `result.json`, parses text/media, runs RAT-FBP, and builds SQLite analytical database + FTS5 full-text tables. |
| `project/scripts/vector_indexer.py` | Generates dense embeddings for conversation threads into SQLite via OpenRouter API or local GPU/CPU. |
| `project/scripts/triage_threads.py` | System-1 Dialogue Thread Triage Engine: classifies threads, filters conversational noise, detects behavioral anomalies and interlocutor shocks. |
| `project/scripts/query_chat.py` | Command-line interface for the analysis agent to extract statistics, analyze silence gaps, search keywords, query triaged threads, and retrieve transcripts. |
| `project/scripts/requirements.txt` | Optional local ML dependencies (`sentence-transformers`). |

---

## 3. Step-by-Step Workflow for the Analysis Agent

Whenever tasked with analyzing a chat export (e.g. located in `rozmowy/` or provided by the user):

### Step 0: Pre-Flight Configuration & Validation (HARD STOP GATE)
Run the validator:
```bash
python3 project/scripts/setup_config.py
```
- **If exit code is 2 (`ACTION_REQUIRED`):** HARD STOP. The API key has not been configured. Prompt the user to enter their API key in `config/embeddings_config.json` (outside the agent folder) and **HALT EXECUTION IMMEDIATELY**. Do not call `db_builder.py`, `query_chat.py`, or any other tool until the user explicitly confirms they have configured the key.
- **If exit code indicates error (3, 4, 5, 6):** HARD STOP. Notify the user of the exact diagnostic error (invalid key, insufficient credits, wrong model, or network failure) and pause.
- **If exit code is 0 (`SUCCESS`):** Configuration and connectivity verified. Proceed to Step 1.

### Step 1: Build the Analytical Database & Clean Slate Protocol
When starting an analysis for a new subject, **always clean previous database state** or create a dedicated database file to prevent cross-subject contamination and statistical noise:
```bash
# Clean slate build for a new subject (RECOMMENDED default to avoid noise):
python3 project/scripts/db_builder.py rozmowy/nowa_osoba.json -o chat.db --clean

# Or isolated database per subject (preserving historical databases):
python3 project/scripts/db_builder.py rozmowy/nowa_osoba.json -o chat_nowa_osoba.db

# Multi-file export for the same person:
python3 project/scripts/db_builder.py rozmowy/osoba_part1.json rozmowy/osoba_part2.json -o chat.db --clean
```
*The `--clean` flag purges existing messages, threads, silence gaps, and embeddings, ensuring statistical baselines (`--stats`, `--timeline`, `--gaps`) remain 100% pure.*

### Step 2: Index Semantic Vectors (MANDATORY PREREQUISITE)
Vector indexing is a **mandatory prerequisite** for qualitative psychological analysis. The agent must **NEVER** skip this step or silently downgrade to lexical FTS5 search without explicit user consent:
```bash
# Indexes all unindexed threads across all chats incrementally:
python3 project/scripts/vector_indexer.py --db chat.db --index

# Or index/filter a specific chat:
python3 project/scripts/vector_indexer.py --db chat.db --index --chat ania
```
*Note: Generating dense vector embeddings allows `query_chat.py --semantic` to retrieve high-level psychological constructs, defensive patterns, and emotional undertones. The agent must verify vector indexing completion before proceeding to analysis.*

### Step 2.5: System-1 Dialogue Thread Triage (MANDATORY PREREQUISITE)
Execute System-1 triage to classify threads, detect behavioral anomalies, and filter noise:
```bash
python3 project/scripts/triage_threads.py --db chat.db
```
*Note: Evaluates threads with sub-second decision models, eliminating ~45–80% of logistical noise while salvaging low-volume quiet disclosures and flagging interlocutor shock (`is_atypical`, `interlocutor_surprised`).*

### Step 3: Phase 1 – Quantitative Mining & Anomaly Reconnaissance
Run the CLI to extract hard statistical facts and review System-1 triage anomalies:
```bash
# List all indexed chats in the database:
python3 project/scripts/query_chat.py --db chat.db --list-chats

# Global overview across all chats combined (includes In-Chat normalized initiative and per-chat breakdowns):
python3 project/scripts/query_chat.py --db chat.db --stats --gaps --timeline --triage-status

# Focused inspection of a specific relationship dyad:
python3 project/scripts/query_chat.py --db chat.db --chat <chat_name_or_id> --stats --gaps

# Review detected behavioral anomalies and interlocutor shocks:
python3 project/scripts/query_chat.py --db chat.db --anomalies-only

# Review acute emotional peaks (grief, euphoria, rage & condolences):
python3 project/scripts/query_chat.py --db chat.db --emotional-peaks

# Review intimate confessions and advice-seeking dilemmas:
python3 project/scripts/query_chat.py --db chat.db --advice-seeking

# Retrieve high-salience triaged threads:
python3 project/scripts/query_chat.py --db chat.db --triaged-threads --limit 25

# Output as structured JSON for fast agent ingestion:
python3 project/scripts/query_chat.py --db chat.db --stats --gaps --timeline --triage-status --json
```

### Step 4: Phase 2 – Qualitative & Evidence Retrieval
The CLI supports simultaneous multi-query execution, batch repeated flags, and JSON output:

```bash
# 1. Multi-keyword search across all chats or filtered by chat:
python3 project/scripts/query_chat.py --db chat.db -s "mama" -s "ojciec" -s "pieniądze"
python3 project/scripts/query_chat.py --db chat.db --chat partner -s "zaufanie" -s "odrzucenie"

# 2. Batch semantic psychological search across all conversations:
python3 project/scripts/query_chat.py --db chat.db \
  --semantic "refusing vulnerability and emotional suppression" \
  --semantic "fear of abandonment and anxious attachment"

# 3. Retrieve specific conversation thread:
python3 project/scripts/query_chat.py --db chat.db -t c_11111_t101 -c 14502

# 4. Comprehensive single-turn exploration with structured JSON:
python3 project/scripts/query_chat.py --db chat.db \
  --stats \
  --gaps \
  -s "przepraszam" \
  --semantic "conflict resolution" \
  --json

# 5. Programmatic batch execution using a JSON plan:
python3 project/scripts/query_chat.py --db chat.db \
  --batch-json '{"stats": true, "search": ["mama", "praca"], "semantic": ["unikanie bliskości"]}' \
  --json
```

---

## 4. SQLite Schema Reference for Custom SQL Queries

The agent can also query `chat.db` directly using SQLite:

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
