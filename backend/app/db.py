"""Хранилище прогресса учеников (SQLite)."""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    grade INTEGER,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
    user_id TEXT NOT NULL REFERENCES users(id),
    problem_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    hints_used INTEGER NOT NULL DEFAULT 0,
    solution_viewed INTEGER NOT NULL DEFAULT 0,
    solved INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    solved_at REAL,
    PRIMARY KEY (user_id, problem_id)
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    seed INTEGER,
    answer TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS hint_cache (
    problem_id TEXT PRIMARY KEY,
    json TEXT NOT NULL,
    model TEXT,
    created_at REAL NOT NULL
);
"""

_lock = threading.Lock()


class DB:
    def __init__(self, path: str | None = None):
        self.path = path or settings.db_path
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        with _lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    # --- пользователи ---
    def create_user(self, name: str, grade: int | None) -> str:
        uid = uuid.uuid4().hex
        with self.tx() as c:
            c.execute(
                "INSERT INTO users (id, name, grade, created_at) VALUES (?, ?, ?, ?)",
                (uid, name, grade, time.time()),
            )
        return uid

    def get_user(self, uid: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    # --- прогресс ---
    def progress(self, uid: str, pid: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM progress WHERE user_id = ? AND problem_id = ?", (uid, pid)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "user_id": uid,
            "problem_id": pid,
            "attempts": 0,
            "hints_used": 0,
            "solution_viewed": 0,
            "solved": 0,
            "points": 0,
            "solved_at": None,
        }

    def all_progress(self, uid: str) -> dict[str, dict]:
        rows = self.conn.execute("SELECT * FROM progress WHERE user_id = ?", (uid,)).fetchall()
        return {r["problem_id"]: dict(r) for r in rows}

    def save_progress(self, p: dict) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT INTO progress (user_id, problem_id, attempts, hints_used, solution_viewed,
                       solved, points, solved_at)
                   VALUES (:user_id, :problem_id, :attempts, :hints_used, :solution_viewed,
                       :solved, :points, :solved_at)
                   ON CONFLICT(user_id, problem_id) DO UPDATE SET
                       attempts = excluded.attempts, hints_used = excluded.hints_used,
                       solution_viewed = excluded.solution_viewed, solved = excluded.solved,
                       points = excluded.points, solved_at = excluded.solved_at""",
                p,
            )

    def log_submission(self, uid: str, pid: str, seed: int | None, answer: str, status: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO submissions (user_id, problem_id, seed, answer, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uid, pid, seed, answer[:200], status, time.time()),
            )

    def problem_stats(self) -> dict[str, tuple[int, int]]:
        """problem_id -> (сколько учеников пробовали, сколько решили)."""
        rows = self.conn.execute(
            "SELECT problem_id, COUNT(*) AS tried, SUM(solved) AS solved FROM progress"
            " WHERE attempts > 0 OR solved = 1 GROUP BY problem_id"
        ).fetchall()
        return {r["problem_id"]: (r["tried"], r["solved"] or 0) for r in rows}

    def leaderboard(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            """SELECT u.id, u.name, u.grade, COALESCE(SUM(p.points), 0) AS points,
                      COALESCE(SUM(p.solved), 0) AS solved
               FROM users u LEFT JOIN progress p ON p.user_id = u.id
               GROUP BY u.id ORDER BY points DESC, solved DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- кэш подсказок, сгенерированных ИИ ---
    def cached_hints(self, pid: str) -> str | None:
        row = self.conn.execute("SELECT json FROM hint_cache WHERE problem_id = ?", (pid,)).fetchone()
        return row["json"] if row else None

    def cache_hints(self, pid: str, data: str, model: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO hint_cache (problem_id, json, model, created_at) VALUES (?, ?, ?, ?)",
                (pid, data, model, time.time()),
            )
