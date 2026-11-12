"""Database schema definitions for System-1 thread triage and enrichment."""

import sqlite3


def init_triage_table(conn: sqlite3.Connection):
    """Ensure the thread_triage table exists in the database with all diagnostic radar columns."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS thread_triage (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        salience_score REAL NOT NULL,
        escalate INTEGER NOT NULL,
        primary_category TEXT NOT NULL,
        confidence REAL NOT NULL,
        reason TEXT,
        is_atypical INTEGER DEFAULT 0,
        interlocutor_surprised INTEGER DEFAULT 0,
        emotional_peak TEXT DEFAULT 'none',
        is_advice_seeking INTEGER DEFAULT 0,
        mentions_third_party INTEGER DEFAULT 0,
        anomaly_notes TEXT,
        raw_response TEXT,
        triaged_at TEXT NOT NULL
    );
    """)

    cur.execute("PRAGMA table_info(thread_triage)")
    existing_cols = {col[1] for col in cur.fetchall()}
    if "is_atypical" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_atypical INTEGER DEFAULT 0")
    if "interlocutor_surprised" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN interlocutor_surprised INTEGER DEFAULT 0")
    if "emotional_peak" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN emotional_peak TEXT DEFAULT 'none'")
    if "is_advice_seeking" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_advice_seeking INTEGER DEFAULT 0")
    if "mentions_third_party" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN mentions_third_party INTEGER DEFAULT 0")
    if "anomaly_notes" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN anomaly_notes TEXT")
    if "summary_short" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN summary_short TEXT")
    if "candidate_entities" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN candidate_entities TEXT")
    if "is_relational_conflict" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_relational_conflict INTEGER DEFAULT 0")
    if "is_medical_or_grief_crisis" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_medical_or_grief_crisis INTEGER DEFAULT 0")
    if "is_bizarre_or_boundary_violation" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_bizarre_or_boundary_violation INTEGER DEFAULT 0")
    if "is_acute_vulnerability_or_breakdown" not in existing_cols:
        cur.execute("ALTER TABLE thread_triage ADD COLUMN is_acute_vulnerability_or_breakdown INTEGER DEFAULT 0")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_escalate ON thread_triage(escalate);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_score ON thread_triage(salience_score);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_atypical ON thread_triage(is_atypical);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_surprised ON thread_triage(interlocutor_surprised);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_peak ON thread_triage(emotional_peak);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_advice ON thread_triage(is_advice_seeking);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_third_party ON thread_triage(mentions_third_party);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_conflict ON thread_triage(is_relational_conflict);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_med_crisis ON thread_triage(is_medical_or_grief_crisis);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_bizarre ON thread_triage(is_bizarre_or_boundary_violation);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triage_vulner ON thread_triage(is_acute_vulnerability_or_breakdown);")
    conn.commit()
