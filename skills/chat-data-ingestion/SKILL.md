---
name: chat-data-ingestion
description: >-
  Ingests, parses, and vectorizes raw Telegram chat exports into SQLite using RAT-FBP threading.
  Use when setting up new chats, building databases, or creating vector embeddings.
---

# Chat Data Ingestion, Indexing & SQLite Architecture Skill

This skill defines the data engineering pipeline, database generation procedures, thread disentanglement engine (RAT-FBP), and SQLite schema reference for processing raw Telegram chat exports.

---

## 1. Overview

Directly ingesting raw JSON chat exports (40,000–50,000+ messages) into LLM context is strictly prohibited. The system converts raw transcripts into an optimized analytical SQLite database (`chat.db`) featuring:
1. **Thread Disentanglement (RAT-FBP):** Reconstructing concurrent discussion topics from interleaved chat streams.
2. **Hybrid Search Indexing:** SQLite FTS5 BM25 full-text search combined with dense vector embeddings.
3. **Automated Salience Triage:** Pre-scoring conversations across behavioral anomalies, emotional peaks, and advice-seeking dilemmas.

---

## 2. When to Use

Activate this skill whenever:
- Ingesting a new Telegram chat export (e.g. JSON file in `rozmowy/` or provided by user).
- Rebuilding or refreshing an analytical database (`chat.db`).
- Generating semantic vector embeddings (`vector_indexer.py --index`).
- Running the System-1 thread triage engine (`triage_threads.py`).
- Writing direct, custom SQLite SQL queries against tables in `chat.db`.

---

## 3. Pre-Flight Configuration Gate (`setup_config.py`)

Before performing any ingestion or indexing, verify environment credentials:

```bash
python3 project/scripts/setup_config.py
```

### Exit Codes & Action Protocol:
- **Code 0 (`SUCCESS`):** Validated. Proceed with database operations.
- **Code 2 (`ACTION_REQUIRED`):** HARD STOP. Prompt user to add their OpenRouter API key to `config/embeddings_config.json`.
- **Codes 3, 4, 5, 6 (`ERROR`):** HARD STOP. Report the exact diagnostic (401 invalid key, 402 insufficient credits, 404 model not found, 6 network failure) to the user.

---

## 4. Database Ingestion Pipeline

### Step 4.1: Parse & Build Analytical Database (`db_builder.py`)
```bash
# Standard incremental build (detects file changes via SHA-256 manifests):
python3 project/scripts/db_builder.py rozmowy/*.json -o chat.db

# Clean rebuild (purges previous messages, threads, and embeddings):
python3 project/scripts/db_builder.py rozmowy/new_chat.json -o chat.db --clean

# Isolated database per subject:
python3 project/scripts/db_builder.py rozmowy/subject.json -o chat_subject.db
```

### Step 4.2: Semantic Vector Indexing (`vector_indexer.py`)
Embeds reconstructed dialogue threads into dense vectors for `--semantic` searches:
```bash
# Generate embeddings using configured OpenRouter model or local PyTorch:
python3 project/scripts/vector_indexer.py --db chat.db --index

# Test vector retrieval directly:
python3 project/scripts/vector_indexer.py --db chat.db --search "fear of intimacy and avoidance"
```

### Step 4.3: System-1 Dialogue Thread Triage & Enrichment (`triage_threads.py`)
Pre-screens conversation threads, populating the `thread_triage` table with Diagnostic Radars and optional LLM summaries/extractions:
```bash
# Standard System-1 triage across all threads:
python3 project/scripts/triage_threads.py --db chat.db

# Enrich salient threads with summaries and entity candidates using configured models:
python3 project/scripts/triage_threads.py --db chat.db --enrich
```
- **Radar 1 (Behavioral Anomalies):** Flags deviant actions (`is_atypical`) and conversational dissonance (`interlocutor_surprised`).
- **Radar 2 (Acute Emotional Peaks):** Flags affective amplitude (`profound_sadness`, `euphoric_joy`, `intense_rage`).
- **Radar 3 (Advice-Seeking Dilemmas):** Flags intimate confessions, existential crises, and advice requests (`is_advice_seeking`).
- **Batch Enrichment (`--enrich`):** Uses `summary_model` and `extraction_model` configured in `config/embeddings_config.json` to generate concise summaries (`summary_short`) and third-party entity candidates (`candidate_entities`).

---

## 5. Thread Disentanglement Engine (RAT-FBP)

The ingestion engine resolves concurrent discussions using **Reply-Anchored Threading with Forward Burst Propagation (RAT-FBP)**:

1. **Explicit Reply (`reply_to_id`):** When a message explicitly quotes an anchor, it attaches directly to that discussion tree.
2. **Forward Burst Continuation:** If the same sender posts subsequent messages within $\le 180$ seconds without quotes, those messages automatically inherit the thread and parent of the active thought.
3. **Inferred Response:** When the interlocutor responds within $\le 60$ minutes (3600 seconds) without an explicit quote, the message links to the active exchange as an inferred turn-taking turn.
4. **Direct Reply Attachment & 50-Message Limit Invariant:** When message B explicitly quotes message A (`reply_to_id = A`), message B attaches to the topic cluster of message A. However, to prevent oversized context monoliths, all conversation threads are capped at a strict maximum of **50 messages** (`MAX_THREAD_MESSAGES = 50`). If an extended discussion exceeds 50 messages, it is deterministically partitioned into linked sequential chunks (`_p2`, `_p3`, etc.) connected via `parent_thread_id`.
5. **Silence Segmentation:** Inactivity gaps $> 2$ hours automatically partition sessions; gaps $> 24$ hours populate the relational `silence_gaps` table.
6. **Chronological Audit Separation:** Threads remain strictly partitioned by topic in SQLite to protect dense vector embedding fidelity. Cross-thread context audits ($\pm 5$ messages at thread boundaries and across parent/child lineage) are performed at query time via `query_chat.py --around <id> -n 5` or `query_chat.py -t <parent_or_child_thread_id>`.

---

## 6. Complete SQLite Database Schema Reference

When executing direct SQL queries against `chat.db`:

### `chats` Table (Catalog of all indexed contacts / conversations)
- `chat_id` (TEXT PRIMARY KEY): Unique chat slug (e.g. `c_11111` or `c_mama`).
- `chat_name` (TEXT): Display name from Telegram export.
- `chat_type` (TEXT): `personal_chat`, `private_group`, etc.
- `source_files` (TEXT): Source JSON file path(s).
- `total_messages`, `total_threads` (INTEGER).
- `start_date`, `end_date` (TEXT ISO8601).

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
- `thread_id` (TEXT PRIMARY KEY): Globally unique thread ID (`<chat_id>_t<id>` or `<chat_id>_t<id>_p<N>`).
- `chat_id` (TEXT): Originating chat stream.
- `parent_thread_id` (TEXT): Pointer to parent thread if partitioned due to the 50-message limit (NULL for root threads).
- `anchor_message_id` (INTEGER): Quoted anchor message ID.
- `start_date`, `end_date` (TEXT): Thread timeframe.
- `message_count` (INTEGER): Number of messages in this topic (capped at 50).
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
- `mentions_third_party` (BOOLEAN): Mentions or discusses external third party (Radar 4).
- `triage_reason` (TEXT): Concise rationale.

### `chat_entities` Table (Registered Third-Party Individuals Scoped to Chat)
- `entity_id` (TEXT NOT NULL): Slugified entity key (e.g. `caleb`, `dustin`).
- `chat_id` (TEXT NOT NULL): Scoped conversation stream (`PRIMARY KEY (chat_id, entity_id)`).
- `name_or_alias` (TEXT NOT NULL): Personal name or alias.
- `verified_role` (TEXT): Verified relationship role (e.g. `ex-partner`, `platonic friend`).
- `associated_descriptors` (TEXT): Geographic, occupational, or social labels (`US guy, Oregon`).
- `is_ex_partner` (INTEGER DEFAULT 0): Explicit binary flag.
- `is_romantic` (INTEGER DEFAULT 0): Explicit binary romantic flag.
- `confidence` (TEXT DEFAULT 'unverified'): Verification status (`verified`, `unverified`, `hypothetical`).
- `first_msg_id` (INTEGER): Message ID introducing the individual.
- `notes` (TEXT): Biographical anchors and disambiguation notes.
- `created_at`, `updated_at` (TEXT ISO8601).

### `chat_descriptors` Table (Audited Role & Geographic Descriptors with Cardinality)
- `chat_id` (TEXT NOT NULL): Scoped conversation stream (`PRIMARY KEY (chat_id, descriptor)`).
- `descriptor` (TEXT NOT NULL): Normalized lowercase descriptor (`sister`, `us guy`).
- `cardinality` (TEXT NOT NULL): `SINGLETON_K1` vs `POLYSEMOUS_K_GT_1` or `UNRESOLVED`.
- `estimated_count` (INTEGER DEFAULT 1): Number of distinct entities sharing this descriptor.
- `mapped_entity_ids` (TEXT): Comma-separated list of mapped entities.
- `evidence_msg_ids` (TEXT): Anchors demonstrating plurality or singleton identity.
- `needs_recheck` (INTEGER DEFAULT 0): Automatically set to 1 on chat file manifest refresh.
- `audited_at` (TEXT ISO8601).

---

## 7. Verification Checklist

Before using the generated database for analysis, verify:
- [ ] Has `setup_config.py` returned exit code 0?
- [ ] Did `db_builder.py` complete without errors?
- [ ] Were dialogue threads vectorized using `vector_indexer.py --index`?
- [ ] Has `triage_threads.py` populated the `thread_triage` table?
- [ ] Does `query_chat.py --db chat.db --stats` show valid non-zero counts?
