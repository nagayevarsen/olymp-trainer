"""Хранилище прогресса учеников (SQLite)."""

from __future__ import annotations

import hashlib
import secrets
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
CREATE TABLE IF NOT EXISTS daily (
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS streaks (
    user_id TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    last_day TEXT,
    restores_left INTEGER NOT NULL DEFAULT 3,
    restores_month TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chat_usage (
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS strong_usage (
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS hint_cache (
    problem_id TEXT PRIMARY KEY,
    json TEXT NOT NULL,
    model TEXT,
    created_at REAL NOT NULL
);
"""

_lock = threading.Lock()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class DB:
    def __init__(self, path: str | None = None):
        self.path = path or settings.db_path
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA foreign_keys=ON")
        # С WAL этого достаточно для надёжности, а записи (каждая попытка ответа) заметно быстрее.
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._stats: dict[str, tuple[int, int]] | None = None
        self._stats_version = 0
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Аккаунты появились позже: добавить ник и хэш пароля в старую таблицу users."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(users)")}
        with self.tx() as c:
            if "nick" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN nick TEXT")
            if "pass_hash" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN pass_hash TEXT")
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS users_nick ON users(nick COLLATE NOCASE) WHERE nick IS NOT NULL"
            )

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

    # --- аккаунты (ник + пароль) ---
    def nick_taken(self, nick: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM users WHERE nick = ? COLLATE NOCASE", (nick,)).fetchone()
        return row is not None

    def create_account(self, nick: str, pass_hash: str, grade: int | None) -> str | None:
        """Новый аккаунт. None — ник уже занят."""
        uid = uuid.uuid4().hex
        try:
            with self.tx() as c:
                c.execute(
                    "INSERT INTO users (id, name, grade, created_at, nick, pass_hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (uid, nick, grade, time.time(), nick, pass_hash),
                )
        except sqlite3.IntegrityError:
            return None
        return uid

    def attach_account(self, uid: str, nick: str, pass_hash: str) -> bool:
        """Привязать ник и пароль к профилю-гостю (прогресс сохраняется). False — ник занят."""
        try:
            with self.tx() as c:
                c.execute(
                    "UPDATE users SET nick = ?, name = ?, pass_hash = ? WHERE id = ?",
                    (nick, nick, pass_hash, uid),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def user_by_nick(self, nick: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE nick = ? COLLATE NOCASE", (nick,)).fetchone()

    def delete_user(self, uid: str) -> None:
        """Удалить аккаунт и всё, что с ним связано."""
        with self.tx() as c:
            for table in (
                "progress",
                "submissions",
                "chat_usage",
                "streaks",
                "daily",
                "sessions",
                "strong_usage",
            ):
                c.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM users WHERE id = ?", (uid,))
            self._invalidate_stats()

    # --- сессии: случайный токен входа (в базе только его хэш), id пользователя секретом не является ---
    def create_session(self, uid: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.tx() as c:
            c.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
                (_token_hash(token), uid, time.time()),
            )
        return token

    def user_by_session(self, token: str, max_age_s: float) -> sqlite3.Row | None:
        row = self.conn.execute(
            "SELECT u.* , s.created_at AS session_created FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = ?",
            (_token_hash(token),),
        ).fetchone()
        if row is None or time.time() - row["session_created"] > max_age_s:
            return None
        return row

    def delete_session(self, token: str) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def delete_other_sessions(self, uid: str, keep_token: str) -> None:
        with self.tx() as c:
            c.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (uid, _token_hash(keep_token))
            )

    def take_strong(self, uid: str, day: str, per_user: int, total: int) -> bool:
        """Занять один запрос к сильной модели (Sonnet), если не исчерпаны личный и общий дневные лимиты."""
        with self.tx() as c:
            mine = c.execute(
                "SELECT requests FROM strong_usage WHERE user_id = ? AND day = ?", (uid, day)
            ).fetchone()
            everyone = c.execute(
                "SELECT COALESCE(SUM(requests), 0) AS n FROM strong_usage WHERE day = ?", (day,)
            ).fetchone()["n"]
            if (mine["requests"] if mine else 0) >= per_user or everyone >= total:
                return False
            c.execute(
                "INSERT INTO strong_usage (user_id, day, requests) VALUES (?, ?, 1) "
                "ON CONFLICT(user_id, day) DO UPDATE SET requests = requests + 1",
                (uid, day),
            )
        return True

    def chat_total(self, day: str) -> int:
        """Сколько запросов к ИИ сделали все ученики за день (защита общего бюджета)."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(messages), 0) AS n FROM chat_usage WHERE day = ?", (day,)
        )
        return int(row.fetchone()["n"])

    def get_daily(self, uid: str, day: str) -> str | None:
        row = self.conn.execute(
            "SELECT problem_id FROM daily WHERE user_id = ? AND day = ?", (uid, day)
        ).fetchone()
        return row["problem_id"] if row else None

    def set_daily(self, uid: str, day: str, pid: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO daily (user_id, day, problem_id) VALUES (?, ?, ?)", (uid, day, pid)
            )

    def get_streak(self, uid: str):
        from datetime import date

        from .streak import StreakState

        row = self.conn.execute("SELECT * FROM streaks WHERE user_id = ?", (uid,)).fetchone()
        if not row:
            return StreakState()
        return StreakState(
            count=row["count"],
            last_day=date.fromisoformat(row["last_day"]) if row["last_day"] else None,
            restores_left=row["restores_left"],
            restores_month=row["restores_month"],
        )

    def save_streak(self, uid: str, st) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO streaks (user_id, count, last_day, restores_left, restores_month) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET count = excluded.count, last_day = excluded.last_day, "
                "restores_left = excluded.restores_left, restores_month = excluded.restores_month",
                (
                    uid,
                    st.count,
                    st.last_day.isoformat() if st.last_day else None,
                    st.restores_left,
                    st.restores_month,
                ),
            )

    def count_chat_message(self, uid: str, day: str) -> int:
        """Учесть сообщение в чат и вернуть, сколько их за день."""
        with self.tx() as c:
            c.execute(
                "INSERT INTO chat_usage (user_id, day, messages) VALUES (?, ?, 1) "
                "ON CONFLICT(user_id, day) DO UPDATE SET messages = messages + 1",
                (uid, day),
            )
        row = self.conn.execute(
            "SELECT messages FROM chat_usage WHERE user_id = ? AND day = ?", (uid, day)
        ).fetchone()
        return int(row["messages"])

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
            self._invalidate_stats()

    def log_submission(self, uid: str, pid: str, seed: int | None, answer: str, status: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO submissions (user_id, problem_id, seed, answer, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uid, pid, seed, answer[:200], status, time.time()),
            )

    def _invalidate_stats(self) -> None:
        self._stats_version += 1
        self._stats = None

    def problem_stats(self) -> dict[str, tuple[int, int]]:
        """problem_id -> (сколько учеников пробовали, сколько решили).

        Нужна почти в каждом запросе, а меняется только при сохранении прогресса — поэтому кэшируется
        и сбрасывается в save_progress / delete_user."""
        cached, version = self._stats, self._stats_version
        if cached is not None:
            return cached
        rows = self.conn.execute(
            "SELECT problem_id, COUNT(*) AS tried, SUM(solved) AS solved FROM progress"
            " WHERE attempts > 0 OR solved = 1 GROUP BY problem_id"
        ).fetchall()
        stats = {r["problem_id"]: (r["tried"], r["solved"] or 0) for r in rows}
        if version == self._stats_version:  # пока считали, прогресс не менялся
            self._stats = stats
        return stats

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
