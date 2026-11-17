---
trigger: always_on
---

# Analytical CLI Engine & Database Query Protocol (Coordinator Tools)

These rules govern database access, macro-analytical exploration tools, diagnostic radars, and programmatic gates executed by the Main Coordinator.

---

## 1. Zero-Context-Pollution & Database Location Standard

1. **Context Protection Mandate:** NEVER load raw chat files (>1,000 messages) directly into context. All exploration operates via CLI queries against analytical SQLite databases.
2. **Standard Database Location:** Workspace root: `chat.db` (or `data/chat.db`).
3. **One-Off Database Setup:** For initial ingestion (`db_builder.py`), database rebuilding, and vector index generation (`vector_indexer.py --index`), activate the `chat-data-ingestion` skill.
4. **Qualitative Search Delegation:** All deep qualitative semantic searches (`--semantic`), thread partition inspections (`-t`), and quote context verifications are executed exclusively by specialized subagents, protecting the Main Coordinator's primary context.

---

## 2. Coordinator Analytical CLI Matrix (`query_chat.py`)

The Main Coordinator executes the following CLI tools during session execution:

### 2.1 Step B.1: Quantitative Relational Mining & Time Metrics
```bash
# Global baselines & dyadic breakdown:
python3 project/scripts/query_chat.py -C "<chat_id>" --stats --gaps

# Silence gaps & tiered initiative tracking (filter for prolonged pauses >= 7 days or >= 30 days):
python3 project/scripts/query_chat.py -C "<chat_id>" --gaps --min-days 7
python3 project/scripts/query_chat.py -C "<chat_id>" --gaps --min-days 30

# Longitudinal density & crisis spike detection:
python3 project/scripts/query_chat.py -C "<chat_id>" --timeline
python3 project/scripts/query_chat.py -C "<chat_id>" --burning-days
```

### 2.2 Step B.1: Diagnostic Salience Radars & Batch Enrichment
```bash
# Salience radar sweeps (System-1 triage orientation):
python3 project/scripts/query_chat.py -C "<chat_id>" --anomalies-only   # Interlocutor shock, call-outs, friction
python3 project/scripts/query_chat.py -C "<chat_id>" --emotional-peaks  # Intense sadness, joy, rage
python3 project/scripts/query_chat.py -C "<chat_id>" --advice-seeking   # Existential dilemmas, intimate confessions
python3 project/scripts/query_chat.py -C "<chat_id>" --triaged-threads --limit 25  # Top scored salience threads

# Scaledown batch enrichment (Extraction for third parties, short summaries for anomalies):
python3 project/scripts/triage_threads.py -C <chat_id> --enrich
```

### 2.3 Step B.5: Programmatic Hard-Stop Gates & Fact Blackboard Inspection
```bash
# Mandatory Triple Hard-Stop Gate Verification (must all exit 0 before Step B.6):
python3 project/scripts/query_chat.py --check-watchdog-gate -C <chat_id>
python3 project/scripts/thread_checklist.py --check -C <chat_id>
python3 project/scripts/checklist.py --check -C <chat_id>

# Fact Blackboard & Cast of Characters Inspection:
python3 project/scripts/query_chat.py -C "<chat_id>" --entities
python3 project/scripts/query_chat.py -C "<chat_id>" --descriptors

# Review Proposed Dynamic Custom Sections:
python3 project/scripts/thread_checklist.py -C <chat_id> --list-custom-sections
```
