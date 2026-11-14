"""SQLite storage for notes, quiz results and exam dates."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "study.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    correct INTEGER NOT NULL,
    taken_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exams (
    subject TEXT PRIMARY KEY,
    exam_date TEXT NOT NULL
);
"""


@contextmanager
def connect():
    """Open the database, make sure tables exist, commit and close afterwards."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect():
        pass


# ---------- notes ----------
def add_note(subject, title, content):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes (subject, title, content, created_at) VALUES (?, ?, ?, ?)",
            (subject.strip(), title.strip(), content, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def list_notes(subject=None):
    with connect() as conn:
        if subject:
            rows = conn.execute("SELECT * FROM notes WHERE subject = ? ORDER BY id DESC", (subject,))
        else:
            rows = conn.execute("SELECT * FROM notes ORDER BY id DESC")
        return [dict(r) for r in rows]


def get_note(note_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None


def delete_note(note_id):
    with connect() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def list_subjects():
    with connect() as conn:
        rows = conn.execute("SELECT DISTINCT subject FROM notes ORDER BY subject")
        return [r["subject"] for r in rows]


# ---------- quiz results ----------
def add_quiz_results(subject, topic, results):
    """results = list of (question_text, was_correct)."""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany(
            "INSERT INTO quiz_results (subject, topic, question, correct, taken_at) VALUES (?, ?, ?, ?, ?)",
            [(subject, topic, q, int(ok), now) for q, ok in results],
        )


def subject_accuracy():
    """{subject: share of quiz answers that were correct (0..1)}"""
    with connect() as conn:
        rows = conn.execute("SELECT subject, AVG(correct) AS acc FROM quiz_results GROUP BY subject")
        return {r["subject"]: r["acc"] for r in rows}


def topic_accuracy(subject):
    """[(topic, accuracy, attempts)] with the weakest topic first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT topic, AVG(correct) AS acc, COUNT(*) AS n FROM quiz_results "
            "WHERE subject = ? GROUP BY topic ORDER BY acc ASC",
            (subject,),
        )
        return [(r["topic"], r["acc"], r["n"]) for r in rows]


# ---------- exams ----------
def set_exam(subject, exam_date):
    with connect() as conn:
        conn.execute(
            "INSERT INTO exams (subject, exam_date) VALUES (?, ?) "
            "ON CONFLICT(subject) DO UPDATE SET exam_date = excluded.exam_date",
            (subject, exam_date.isoformat()),
        )


def list_exams():
    with connect() as conn:
        rows = conn.execute("SELECT subject, exam_date FROM exams ORDER BY exam_date")
        return [{"subject": r["subject"], "exam_date": date.fromisoformat(r["exam_date"])} for r in rows]


def delete_exam(subject):
    with connect() as conn:
        conn.execute("DELETE FROM exams WHERE subject = ?", (subject,))
