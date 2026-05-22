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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                pnr_number TEXT PRIMARY KEY,
                train_number TEXT,
                train_name TEXT,
                date TEXT,
                travel_class TEXT,
                passenger_name TEXT,
                age INTEGER,
                status TEXT,
                coach TEXT,
                berth INTEGER
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

def save_booking(booking: dict):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO bookings (
                pnr_number, train_number, train_name, date, travel_class, passenger_name, age, status, coach, berth
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            booking.get("pnr_number"),
            booking.get("train_number"),
            booking.get("train_name", ""),
            booking.get("date"),
            booking.get("travel_class"),
            booking.get("passenger"),
            booking.get("age"),
            booking.get("status", "CONFIRMED"),
            booking.get("coach"),
            booking.get("berth")
        ))
        conn.commit()

def get_booking(pnr_number: str) -> dict:
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings WHERE pnr_number = ?", (pnr_number,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_all_bookings() -> list:
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_all_sessions() -> list:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, history FROM sessions")
        rows = cursor.fetchall()
        sessions = []
        for row in rows:
            sid = row[0]
            history = json.loads(row[1]) if row[1] else []
            # Extract a brief title/preview from history
            title = "New Conversation"
            date_meta = ""
            for msg in history:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # Strip out ui-data JSON if present
                    if "```ui-data" in content:
                        content = content.split("```ui-data")[0].strip()
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    break
            sessions.append({
                "session_id": sid,
                "title": title
            })
        return sessions

