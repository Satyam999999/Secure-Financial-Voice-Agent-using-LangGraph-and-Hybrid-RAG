import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
import config

# Paths
BASE_DIR   = Path(config.BASE_DIR)
LOG_DIR    = BASE_DIR / "logs"
LOG_FILE   = LOG_DIR / "interactions.jsonl"
DB_PATH    = BASE_DIR / "data" / "interactions.db"

LOG_DIR.mkdir(exist_ok=True)

# ── SQLite setup ───────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            timestamp   TEXT,
            question    TEXT,
            intent      TEXT,
            answer      TEXT,
            tool_used   TEXT,
            blocked     INTEGER,
            num_chunks  INTEGER,
            sources     TEXT,
            error       TEXT,
            flagged     INTEGER DEFAULT 0,
            flag_reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT,
            timestamp       TEXT,
            reason          TEXT,
            conversation    TEXT,
            status          TEXT DEFAULT 'pending',
            agent_response  TEXT,
            resolved_at     TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Tables ready.")

# ── Log a full interaction ─────────────────────────────────────
def log_interaction(
    session_id: str,
    question: str,
    intent: str,
    answer: str,
    tool_used: str = None,
    blocked: bool = False,
    num_chunks: int = 0,
    sources: list = None,
    error: str = None,
    flagged: bool = False,
    flag_reason: str = None,
):
    timestamp = datetime.utcnow().isoformat()

    record = {
        "session_id": session_id,
        "timestamp":  timestamp,
        "question":   question,
        "intent":     intent,
        "answer":     answer[:300],  # truncate for log
        "tool_used":  tool_used,
        "blocked":    blocked,
        "num_chunks": num_chunks,
        "sources":    sources or [],
        "error":      error,
        "flagged":    flagged,
        "flag_reason": flag_reason,
    }

    # ── Write to JSONL file ────────────────────────────────────
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

    # ── Write to SQLite ────────────────────────────────────────
    conn = get_db()
    conn.execute("""
        INSERT INTO interactions
        (session_id, timestamp, question, intent, answer, tool_used,
         blocked, num_chunks, sources, error, flagged, flag_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, timestamp, question, intent, answer[:300],
        tool_used, int(blocked), num_chunks,
        json.dumps(sources or []), error,
        int(flagged), flag_reason,
    ))
    conn.commit()
    conn.close()

# ── Log an escalation ─────────────────────────────────────────
def log_escalation(session_id: str, reason: str, conversation: list):
    timestamp = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO escalations (session_id, timestamp, reason, conversation, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (session_id, timestamp, reason, json.dumps(conversation)))
    conn.commit()
    conn.close()

# ── Analytics queries ─────────────────────────────────────────
def get_stats() -> dict:
    conn = get_db()

    total      = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    blocked    = conn.execute("SELECT COUNT(*) FROM interactions WHERE blocked=1").fetchone()[0]
    flagged    = conn.execute("SELECT COUNT(*) FROM interactions WHERE flagged=1").fetchone()[0]
    escalations= conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
    pending_esc= conn.execute("SELECT COUNT(*) FROM escalations WHERE status='pending'").fetchone()[0]

    intents = conn.execute("""
        SELECT intent, COUNT(*) as cnt
        FROM interactions
        GROUP BY intent
        ORDER BY cnt DESC
    """).fetchall()

    recent = conn.execute("""
        SELECT session_id, timestamp, question, intent, blocked, flagged
        FROM interactions
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return {
        "total":         total,
        "blocked":       blocked,
        "flagged":       flagged,
        "escalations":   escalations,
        "pending_escalations": pending_esc,
        "blocked_pct":   round(blocked / total * 100, 1) if total else 0,
        "intents":       [dict(r) for r in intents],
        "recent":        [dict(r) for r in recent],
    }

def get_escalations(status: str = "pending") -> list:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM escalations
        WHERE status = ?
        ORDER BY id DESC
    """, (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_escalation(esc_id: int, agent_response: str):
    conn = get_db()
    conn.execute("""
        UPDATE escalations
        SET status='resolved', agent_response=?, resolved_at=?
        WHERE id=?
    """, (agent_response, datetime.utcnow().isoformat(), esc_id))
    conn.commit()
    conn.close()