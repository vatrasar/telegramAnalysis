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
3. **Anchor Resolution:** The originating message quoted at the beginning of a thread is included as the header anchor in the transcript, ensuring full contextual readability.
4. **Silence Segmentation:** Inactivity gaps $> 2$ hours automatically partition sessions, while gaps $> 24$ hours populate the relational `silence_gaps` table.

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
| `project/scripts/query_chat.py` | Command-line interface for the analysis agent to extract statistics, analyze silence gaps, search keywords, and retrieve full threads. |
| `project/scripts/vector_indexer.py` | Generates dense embeddings for conversation threads into SQLite via OpenRouter API or local GPU/CPU. |
| `project/scripts/requirements.txt` | Optional local ML dependencies (`sentence-transformers`). |

---

## 3. Step-by-Step Workflow for the Analysis Agent

Whenever tasked with analyzing a chat export (e.g. located in `rozmowy/` or provided by the user):

### Step 0: Pre-Flight Configuration & Validation
Run the validator:
```bash
python3 project/scripts/setup_config.py
```
- If exit code is 2 (`ACTION_REQUIRED`): Prompt the user to enter their API key in `config/embeddings_config.json` (outside agent folder) and pause until confirmed.
- If exit code indicates error (3, 4, 5, 6): Notify the user of the exact error (invalid key, insufficient credits, wrong model, or network).
- If exit code is 0 (`SUCCESS`): Proceed to Step 1.

### Step 1: Build the Analytical Database
Execute the database builder in bash:
```bash
python3 project/scripts/db_builder.py <path/to/result.json> -o chat.db
```
*Creates `chat.db` with indexed messages, disentangled threads, silence gaps, and FTS5 search.*

### Step 2: (Optional) Index Semantic Vectors (OpenRouter or Local)
If `config/embeddings_config.json` is configured with OpenRouter API key, or if local `sentence-transformers` is installed:
```bash
python3 project/scripts/vector_indexer.py --db chat.db --index
```
*(Note: If not configured, `query_chat.py` automatically falls back to SQLite FTS5 BM25 search with zero errors).*

### Step 3: Phase 1 – Quantitative Mining
Run the CLI to extract hard statistical facts before doing psychological interpretation:
```bash
# Combine multiple metrics in a single execution:
python3 project/scripts/query_chat.py --db chat.db --stats --gaps --timeline

# Or output as structured JSON for fast agent ingestion:
python3 project/scripts/query_chat.py --db chat.db --stats --gaps --timeline --json
```

### Step 4: Phase 2 – Qualitative & Evidence Retrieval
The CLI supports simultaneous multi-query execution, batch repeated flags, and JSON output:

```bash
# 1. Multi-keyword search across messages or threads in one call:
python3 project/scripts/query_chat.py --db chat.db -s "mama" -s "ojciec" -s "pieniądze"

# 2. Batch semantic psychological search in a single pass:
python3 project/scripts/query_chat.py --db chat.db \
  --semantic "refusing vulnerability and emotional suppression" \
  --semantic "fear of abandonment and anxious attachment"

# 3. Retrieve multiple threads or quote chains simultaneously:
python3 project/scripts/query_chat.py --db chat.db -t thread_101 -t 14502 -c 14502

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

The agent can also query `project/data/chat.db` directly using SQLite:

### `messages` Table
- `id` (INTEGER): Message ID from Telegram.
- `date` (TEXT): ISO8601 timestamp (`YYYY-MM-DDTHH:MM:SS`).
- `sender` (TEXT): Sender display name.
- `reply_to_id` (INTEGER): Quoted message ID (if any).
- `thread_id` (TEXT): Assigned conversation thread identifier.
- `link_type` (TEXT): `explicit_reply`, `burst_continuation`, `inferred_response`, or `session_root`.
- `text` (TEXT): Plain message text.
- `char_count`, `word_count` (INTEGER).

### `threads` Table
- `thread_id` (TEXT): Unique thread ID (e.g. `thread_101` or `session_500`).
- `anchor_message_id` (INTEGER): Quoted anchor message ID.
- `start_date`, `end_date` (TEXT): Thread timeframe.
- `message_count` (INTEGER): Number of messages in this topic.
- `participants` (TEXT): Comma-separated list of participants.
- `initiator` (TEXT): Who started or quoted the thread.
- `dialogue_text` (TEXT): Reconstructed transcript ready for LLM consumption.

### `silence_gaps` Table
- `silence_start_date`, `silence_end_date` (TEXT): Inactivity timeframe.
- `silence_duration_hours` (REAL): Duration in hours.
- `last_sender` (TEXT): Who sent the last message before silence.
- `initiator` (TEXT): Who sent the first message breaking the silence.
