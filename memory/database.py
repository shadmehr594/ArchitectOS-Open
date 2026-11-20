# ArchitectOS - memory/database.py
# Core Memory Database Layer (SQLite)

import sqlite3
from pathlib import Path
from datetime import datetime

from config import PATHS


# =========================
# Database Path
# =========================

DB_PATH = PATHS["database"] / "memory.db"


# =========================
# Init Database
# =========================

def connect():
    """Create and return DB connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize memory database tables."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# =========================
# Save Memory
# =========================

def save_message(role: str, message: str):
    """Save a message to memory."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO conversations (role, message, timestamp)
        VALUES (?, ?, ?)
    """, (
        role,
        message,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================
# Load Memory
# =========================

def load_recent(limit: int = 10):
    """Load recent conversations."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, message, timestamp
        FROM conversations
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return list(reversed(rows))


# =========================
# Clear Memory (optional)
# =========================

def clear_memory():
    """Clear all stored conversations."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM conversations")

    conn.commit()
    conn.close()


# =========================
# Auto Init
# =========================

init_db()