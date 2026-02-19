"""
SQLite database layer for AVA's memory system.
Stores conversations, feedback, and style profile data.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "memory" / "ava_memory.db"


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # ── Conversations ────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            user_message    TEXT NOT NULL,
            model_response  TEXT NOT NULL,
            user_correction TEXT,
            feedback_score  REAL DEFAULT 0.0,
            feedback_label  TEXT,
            style_tags      TEXT DEFAULT '[]',
            embedding_id    INTEGER,
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_used_in_training INTEGER DEFAULT 0
        )
    """)

    # ── Style profile (single-row config) ───────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS style_profile (
            id                      INTEGER PRIMARY KEY DEFAULT 1,
            avg_sentence_length     REAL DEFAULT 15.0,
            directness_score        REAL DEFAULT 0.5,
            formality_score         REAL DEFAULT 0.5,
            emotional_intensity     REAL DEFAULT 0.5,
            vocabulary_richness     REAL DEFAULT 0.5,
            preferred_topics        TEXT DEFAULT '[]',
            communication_patterns  TEXT DEFAULT '{}',
            last_updated            DATETIME DEFAULT CURRENT_TIMESTAMP,
            version                 INTEGER DEFAULT 1
        )
    """)

    # ── Feedback events ──────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER REFERENCES conversations(id),
            feedback_type   TEXT NOT NULL,
            feedback_score  REAL NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Training runs ────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            adapter_version TEXT NOT NULL,
            dataset_size    INTEGER,
            base_model      TEXT,
            training_config TEXT DEFAULT '{}',
            status          TEXT DEFAULT 'pending',
            started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at    DATETIME,
            notes           TEXT
        )
    """)

    # ── Seed default style profile ───────────────────────────────────────────
    cursor.execute("""
        INSERT OR IGNORE INTO style_profile (id) VALUES (1)
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialised at {DB_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation CRUD
# ─────────────────────────────────────────────────────────────────────────────

def save_conversation(
    session_id: str,
    user_message: str,
    model_response: str,
    style_tags: Optional[List[str]] = None,
) -> int:
    """Persist a new conversation turn and return its row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO conversations
               (session_id, user_message, model_response, style_tags)
               VALUES (?, ?, ?, ?)""",
            (session_id, user_message, model_response,
             json.dumps(style_tags or [])),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_feedback(
    conversation_id: int,
    feedback_label: str,
    feedback_score: float,
    user_correction: Optional[str] = None,
):
    """Attach feedback to an existing conversation turn."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE conversations
               SET feedback_label = ?, feedback_score = ?, user_correction = ?
               WHERE id = ?""",
            (feedback_label, feedback_score, user_correction, conversation_id),
        )
        conn.execute(
            """INSERT INTO feedback_events
               (conversation_id, feedback_type, feedback_score)
               VALUES (?, ?, ?)""",
            (conversation_id, feedback_label, feedback_score),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_conversations(limit: int = 20, session_id: Optional[str] = None) -> List[Dict]:
    """Fetch recent conversation turns, optionally scoped to a session."""
    conn = get_connection()
    try:
        if session_id:
            rows = conn.execute(
                """SELECT * FROM conversations WHERE session_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_high_quality_examples(min_score: float = 0.7, limit: int = 500) -> List[Dict]:
    """Return examples suitable for LoRA fine-tuning (high-score or corrected)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM conversations
               WHERE (feedback_score >= ? OR user_correction IS NOT NULL)
               AND is_used_in_training = 0
               ORDER BY feedback_score DESC
               LIMIT ?""",
            (min_score, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_as_trained(conversation_ids: List[int]):
    """Flag conversations as used in a training run."""
    if not conversation_ids:
        return
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(conversation_ids))
        conn.execute(
            f"UPDATE conversations SET is_used_in_training = 1 WHERE id IN ({placeholders})",
            conversation_ids,
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Style profile
# ─────────────────────────────────────────────────────────────────────────────

def get_style_profile() -> Dict[str, Any]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM style_profile WHERE id = 1").fetchone()
        if row is None:
            return {}
        profile = dict(row)
        profile["preferred_topics"] = json.loads(profile.get("preferred_topics") or "[]")
        profile["communication_patterns"] = json.loads(profile.get("communication_patterns") or "{}")
        return profile
    finally:
        conn.close()


def update_style_profile(updates: Dict[str, Any]):
    """Merge partial updates into the style profile."""
    profile = get_style_profile()
    profile.update(updates)
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE style_profile SET
               avg_sentence_length = ?,
               directness_score = ?,
               formality_score = ?,
               emotional_intensity = ?,
               vocabulary_richness = ?,
               preferred_topics = ?,
               communication_patterns = ?,
               last_updated = CURRENT_TIMESTAMP,
               version = version + 1
               WHERE id = 1""",
            (
                profile.get("avg_sentence_length", 15.0),
                profile.get("directness_score", 0.5),
                profile.get("formality_score", 0.5),
                profile.get("emotional_intensity", 0.5),
                profile.get("vocabulary_richness", 0.5),
                json.dumps(profile.get("preferred_topics", [])),
                json.dumps(profile.get("communication_patterns", {})),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Training runs
# ─────────────────────────────────────────────────────────────────────────────

def log_training_run(adapter_version: str, dataset_size: int,
                     base_model: str, config: Dict) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO training_runs
               (adapter_version, dataset_size, base_model, training_config)
               VALUES (?, ?, ?, ?)""",
            (adapter_version, dataset_size, base_model, json.dumps(config)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_training_run(run_id: int, status: str, notes: str = ""):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE training_runs SET status = ?, completed_at = CURRENT_TIMESTAMP,
               notes = ? WHERE id = ?""",
            (status, notes, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_training_history() -> List[Dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM training_runs ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
