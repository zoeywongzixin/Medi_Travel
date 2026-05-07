import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mock_db.sqlite")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            status TEXT,
            condition TEXT,
            hospital TEXT,
            flight TEXT,
            charity TEXT,
            urgency TEXT,
            feedback TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_match(session_id: str, status: str, condition: str, hospital: str, flight: str, charity: str, urgency: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO matches (session_id, status, condition, hospital, flight, charity, urgency, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, status, condition, hospital, flight, charity, urgency, ""))
    match_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return match_id

def update_feedback(match_id: int, feedback: str, new_status: str = "edited"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE matches SET feedback = ?, status = ? WHERE id = ?
    ''', (feedback, new_status, match_id))
    conn.commit()
    conn.close()

def get_few_shot_feedback(condition: str) -> List[Dict[str, Any]]:
    """Returns previous feedback given by doctors for similar conditions."""
    conn = get_connection()
    cursor = conn.cursor()
    # Simple LIKE matching for the condition
    cursor.execute('''
        SELECT condition, feedback FROM matches 
        WHERE status = 'edited' AND feedback != '' AND condition LIKE ?
        LIMIT 5
    ''', (f"%{condition}%",))
    rows = cursor.fetchall()
    conn.close()
    return [{"condition": r["condition"], "feedback": r["feedback"]} for r in rows]

# Initialize on import
init_db()
