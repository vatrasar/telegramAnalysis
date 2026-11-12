---
trigger: always_on
---

# Information Search, Entity Grounding & Chat Q&A Pipeline

These rules define the operational pipeline for searching information, answering user questions about chat history, performing entity grounding to prevent hallucinations, and conducting incremental updates.

---

## 1. Architectural Boundary & Stateless Agent Principle

- The `project/` directory represents the **Agent Package** (skills, rules, scripts).
- **NEVER create runtime databases (`*.db`), user secrets, or runtime artifacts inside `project/`.**
- All runtime user configuration lives in `config/` in the workspace root (e.g. `config/embeddings_config.json`).
- All analytical databases and runtime data live in the workspace root (e.g. `chat.db` or `data/chat.db`).
- All processing scripts in `project/scripts/` read and write runtime state in the parent workspace root.

### 1.1 Prohibition on Ad-Hoc Python/SQLite Querying Scripts
- **Absolute Prohibition:** The agent is strictly forbidden from writing or executing ad-hoc Python one-liners (`python3 -c "import sqlite3..."`), temporary scrapers, or raw SQL scripts to query, search, or slice chat messages.
- **Sanctioned Toolchain:** All exploration, searching, sender filtering, thread reading, and context audits MUST be conducted exclusively via the sanctioned CLI toolchain (`project/scripts/query_chat.py`).

---

## 2. Pre-Flight Configuration Gate

Before performing any ingestion, indexing, or chat analysis, verify configuration:
```bash
python3 project/scripts/setup_config.py
```
- **Exit Code 0 (`SUCCESS`):** Verified. Proceed with queries.
- **Exit Code 2 (`ACTION_REQUIRED`):** Halt immediately and prompt the user to configure `config/embeddings_config.json` with their OpenRouter API key.
- **Exit Codes 3–6 (`ERROR`):** Report exact diagnostic (auth, credits, model, network) and halt.

---

## 3. Initial Chat Invocation & Person Scanning Protocol

When an agent interacts with a chat for the first time, it **MUST** perform an entity scan of the people appearing in that chat. 

### 3.1 Why Person Scanning is Mandatory
In chat logs, participants frequently discuss third parties (ex-partners, coworkers, bosses, family, friends, acquaintances). Without an initial person scan:
- The model routinely suffers from **identity confusion and hallucinations** (e.g. attributing a third party's job, illness, breakup, or eccentric behavior to one of the main chat participants).
- An established entity registry provides the essential ground truth of who is who in the dialogue.

### 3.2 First-Run Scan Procedure
1. **Identify Participants & Existing Entities:**
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --entities
   python3 project/scripts/query_chat.py -C <chat_id> --watchdog-status
   ```
2. **Execute Entity Scan:**
   Run the sequential watchdog scan over threads to identify and register external persons:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan
   ```
   If a new entity is detected, register it with its name/alias and role:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --register-entity "<Name>" --role "<Role/Relationship>"
   ```
   Resume scanning until the pending threads are cleared or reviewed.

---

## 4. Incremental Chat Updates (Delta Entity Scan)

When a chat log is updated with newly exported messages:
1. Update SQLite and vector index:
   ```bash
   python3 project/scripts/db_builder.py
   python3 project/scripts/vector_indexer.py --incremental
   ```
2. **Scan ONLY Newly Arrived Threads:**
   Run the entity scan:
   ```bash
   python3 project/scripts/query_chat.py -C <chat_id> --watchdog-scan
   ```
   `thread_entity_audit` automatically tracks all previously audited threads (`cleared` / `skipped`). The scan will **ONLY** inspect newly added threads, ensuring fast, incremental synchronization of new people and relational figures without re-scanning historical data.

---

## 5. Semantic Search Priority & Query Synergy

The agent must strongly prioritize **semantic search** as the primary discovery mechanism for open inquiries.

### 5.1 Semantic Search (`--semantic` / `-sem`)
Natural conversation in Telegram uses slang, metaphors, emotional shifts, and varied phrasing. Keyword search frequently misses critical discussions because words don't match literally.
- **Use Semantic Search For:**
  - Conceptual queries (*"discussions about moving abroad"*, *"conflicts regarding money"*, *"feeling unappreciated"*).
  - Mood and attitude changes (*"apologies and reconciliations"*, *"moments of extreme stress"*).
  - Paraphrased events (*"trips and holidays"*, *"medical problems"*, *"job interviews"*).
- **Execution:**
  ```bash
  python3 project/scripts/query_chat.py -C <chat_id> --semantic "<descriptive concept or question>" -n 10
  ```

### 5.2 Lexical & Phrase Search (`-s`, `--search`)
Use full-text search (FTS5) to complement semantic search when:
- Searching for specific proper nouns, handles, nicknames, or account names.
- Locating exact quotes, specific numbers, addresses, URLs, or distinct dates.
- Filtering by specific sender (`-S "<Name>"`).
```bash
python3 project/scripts/query_chat.py -C <chat_id> -s "<exact term or phrase>" -S "<sender>" -n 10
```

### 5.3 Mandatory Bidirectional Context Audit ($N-5 \dots N+5$)
Search results (whether semantic or FTS) are discovery pointers, NEVER final evidence.
Whenever a relevant match is located:
```bash
python3 project/scripts/query_chat.py -C <chat_id> --around <message_id> -n 5
```
Or view the full thread:
```bash
python3 project/scripts/query_chat.py -C <chat_id> -t <thread_id>
```
Verify the speaker, the context, whether forwarded or quoted, and whether confirmed or rebutted in subsequent turns ($N+1 \dots N+5$).

---

## 6. Grounded Answering Standards

- **Concise & Direct:** Answer the user's specific inquiry directly and clearly.
- **Exact Chronological Anchors:** Every referenced fact, claim, or quote must include exact citations: `[#<msg_id> | YYYY-MM-DD]`.
- **Entity Accuracy:** Explicitly distinguish between dialogue participants (`sender`) and discussed third parties.
- **No Unsolicited Profiling:** In this mode, do NOT conduct unsolicited personality assessments, Big Five scores, attachment style diagnoses, or psychological profiling unless specifically asked for. Focus on high-fidelity factual truth.
