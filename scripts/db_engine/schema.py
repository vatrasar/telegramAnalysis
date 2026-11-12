"""Database schema definitions, indexes, and full-text search tables."""

import sqlite3


def create_schema(conn: sqlite3.Connection):
    """Initialize relational and FTS5 tables in SQLite with multi-chat support."""
    cur = conn.cursor()

    # Chats catalog
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id TEXT PRIMARY KEY,
        chat_name TEXT NOT NULL,
        chat_type TEXT,
        source_files TEXT NOT NULL,
        total_messages INTEGER NOT NULL,
        total_threads INTEGER NOT NULL,
        start_date TEXT,
        end_date TEXT
    );
    """)

    # Source files manifest for delta tracking & caching
    cur.execute("""
    CREATE TABLE IF NOT EXISTS source_files_manifest (
        file_path TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        last_modified TEXT NOT NULL,
        message_count INTEGER NOT NULL,
        max_message_id INTEGER,
        ingested_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_manifest_chat ON source_files_manifest(chat_id);")

    # Metadata table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # Messages table (composite primary key on chat_id + message id)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        chat_id TEXT NOT NULL,
        id INTEGER NOT NULL,
        date TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        sender TEXT NOT NULL,
        sender_id TEXT,
        reply_to_id INTEGER,
        thread_id TEXT NOT NULL,
        parent_id INTEGER,
        link_type TEXT NOT NULL,
        text TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        word_count INTEGER NOT NULL,
        PRIMARY KEY (chat_id, id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_thread ON messages(chat_id, thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_sender ON messages(chat_id, sender);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_reply ON messages(chat_id, reply_to_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread_global ON messages(thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts_global ON messages(timestamp);")

    # Threads table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        parent_thread_id TEXT,
        anchor_message_id INTEGER,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        start_timestamp INTEGER NOT NULL,
        end_timestamp INTEGER NOT NULL,
        duration_seconds INTEGER NOT NULL,
        message_count INTEGER NOT NULL,
        participants TEXT NOT NULL,
        initiator TEXT NOT NULL,
        gap_before_seconds INTEGER,
        dialogue_text TEXT NOT NULL,
        content_hash TEXT
    );
    """)
    # Migration check for threads table
    cur.execute("PRAGMA table_info(threads);")
    t_cols = {col[1] for col in cur.fetchall()}
    if "content_hash" not in t_cols:
        cur.execute("ALTER TABLE threads ADD COLUMN content_hash TEXT;")
    if "parent_thread_id" not in t_cols:
        cur.execute("ALTER TABLE threads ADD COLUMN parent_thread_id TEXT;")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_chat ON threads(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_parent ON threads(parent_thread_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_start ON threads(start_timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_threads_gap ON threads(gap_before_seconds);")

    # Silence / Gaps table (calculated strictly within each individual chat)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS silence_gaps (
        gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        silence_start_date TEXT NOT NULL,
        silence_end_date TEXT NOT NULL,
        silence_duration_seconds INTEGER NOT NULL,
        silence_duration_hours REAL NOT NULL,
        last_sender TEXT NOT NULL,
        initiator TEXT NOT NULL,
        after_thread_id TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gaps_chat ON silence_gaps(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gaps_duration ON silence_gaps(silence_duration_seconds);")

    # Full-Text Search (FTS5) for messages
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message_id UNINDEXED,
        chat_id UNINDEXED,
        date UNINDEXED,
        sender UNINDEXED,
        thread_id UNINDEXED,
        text,
        tokenize = 'unicode61'
    );
    """)

    # Full-Text Search (FTS5) for threads
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
        thread_id UNINDEXED,
        chat_id UNINDEXED,
        start_date UNINDEXED,
        participants UNINDEXED,
        dialogue_text,
        tokenize = 'unicode61'
    );
    """)

    # Chat scoped third-party entities table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_entities (
        entity_id TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        name_or_alias TEXT NOT NULL,
        verified_role TEXT,
        associated_descriptors TEXT,
        is_ex_partner INTEGER DEFAULT 0,
        is_romantic INTEGER DEFAULT 0,
        confidence TEXT DEFAULT 'unverified',
        first_msg_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, entity_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_chat ON chat_entities(chat_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON chat_entities(chat_id, name_or_alias);")

    # Chat scoped role descriptors & cardinality table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_descriptors (
        chat_id TEXT NOT NULL,
        descriptor TEXT NOT NULL,
        cardinality TEXT NOT NULL,
        estimated_count INTEGER DEFAULT 1,
        mapped_entity_ids TEXT,
        evidence_msg_ids TEXT,
        needs_recheck INTEGER DEFAULT 0,
        audited_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, descriptor)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_desc_chat ON chat_descriptors(chat_id);")

    # Life spheres investigation checklist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS life_spheres_checklist (
        chat_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        sphere_id TEXT NOT NULL,
        sphere_name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_item TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        evidence_summary TEXT,
        query_terms_used TEXT,
        semantic_queries_used TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, item_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_status ON life_spheres_checklist(chat_id, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checklist_chat_sphere ON life_spheres_checklist(chat_id, sphere_id);")

    conn.commit()
