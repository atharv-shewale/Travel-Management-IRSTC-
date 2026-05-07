import sqlite3
import json
from contextlib import contextmanager
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "chatbot.db")

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                history TEXT
            )
        ''')
        conn.commit()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def get_history(session_id: str) -> list:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT history FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return []

def save_history(session_id: str, history: list):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (session_id, history)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET history=excluded.history
        ''', (session_id, json.dumps(history)))
        conn.commit()
