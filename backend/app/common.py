"""Общий код: база, вход по токену, лимиты, подсказки, баллы — нужен нескольким разделам API."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from fastapi import Depends, Header, HTTPException, Request

from . import ai, chat, formula, scoring, streak
from . import ratelimit as rl
from .bank import (
    STAGE_NAMES,
    Hints,
    Problem,
    get_problem,
    load_bank,
)
from .checker import AnswerKey, check_answer
from .cloner import make_variant
from .config import settings
from .db import DB
from .llm import LLMError

log = logging.getLogger("olymp")
SEED_MAX = 2**31 - 1


_db: DB | None = None


def get_db() -> DB:
    global _db
    if _db is None:
        _db = DB()
    return _db


def set_db(db: DB) -> None:
    """Для тестов: подменить базу."""
    global _db
    _db = db


def _bearer(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and 20 <= len(token) <= 200 else ""


def optional_user(authorization: str = Header(default=""), db: DB = Depends(get_db)) -> dict | None:
    """Пользователь по токену сессии (Authorization: Bearer …). id пользователя секретом не является."""
    token = _bearer(authorization)
    row = db.user_by_session(token, settings.session_days * 86_400) if token else None
    return dict(row) if row else None


def current_user(user: dict | None = Depends(optional_user)) -> dict:
    if not user:
        raise HTTPException(401, "Нужно войти в аккаунт")
    return user


def _uid(user: dict | None) -> str:
    return user["id"] if user else ""


def _signup_guard(request: Request) -> None:
    rl.enforce(
        "signup",
        rl.client_ip(request),
        settings.signups_per_ip_hour,
        3600,
        "Слишком много новых аккаунтов с этого адреса. Попробуй через час.",
    )


def _spend_ai(user: dict, request: Request, db: DB, n: int = 1) -> int:
    """Учесть n запросов к ИИ: личный дневной лимит, лимит на IP и общий бюджет сервера."""
    day = time.strftime("%Y-%m-%d")
    if db.chat_total(day) + n > settings.ai_global_daily_limit:
        raise HTTPException(503, "ИИ-помощник на сегодня исчерпал общий лимит. Попробуй завтра.")
    for _ in range(n):
        rl.enforce(
            "ai-ip",
            rl.client_ip(request),
            chat.DAILY_LIMIT * 10,
            86_400,
            "Слишком много запросов с этого адреса",
        )
    used = 0
    for _ in range(n):
        used = db.count_chat_message(user["id"], day)
    if used > chat.DAILY_LIMIT:
        raise HTTPException(
            429, f"На сегодня лимит {chat.DAILY_LIMIT} сообщений помощнику. Возвращайся завтра!"
        )
    return used


def require_problem(problem_id: str) -> Problem:
    p = get_problem(problem_id)
    if not p:
        raise HTTPException(404, "Задача не найдена")
    return p


def problem_points(p: Problem, stats: dict[str, tuple[int, int]]) -> int:
    tried, solved = stats.get(p.id, (0, 0))
    return scoring.dynamic_points(scoring.base_points(p), tried, solved)


def solve_rate(p: Problem, stats: dict[str, tuple[int, int]]) -> int | None:
    tried, solved = stats.get(p.id, (0, 0))
    return round(100 * solved / tried) if tried else None


def track_info(p: Problem) -> dict:
    return {"id": p.source.track_id, "title": p.source.track_title()}


def figure_urls(p: Problem) -> list[str]:
    return [f"/figures/{name}" for name in p.figures]


def source_info(p: Problem) -> dict:
    return {
        "label": p.source.label(),
        "stage": STAGE_NAMES[p.source.stage],
        "url": p.source.url,
        "russian": p.source.russian,
    }


def _today():
    from datetime import date

    return date.today()


def _daily_problem_id(user: dict, db: DB) -> str | None:
    """Задача дня: нерешённая, средней сложности (5–7 из 10), по возможности для класса ученика."""
    stats = db.problem_stats()
    solved = {pid for pid, pr in db.all_progress(user["id"]).items() if pr["solved"]}
    lo, hi = streak.DAILY_POINTS
    pool = [
        p
        for p in load_bank().values()
        if p.id not in solved
        and not p.source.olympiad.startswith("Демо")
        and not p.is_proof
        and lo <= problem_points(p, stats) <= hi
    ]
    if user["grade"]:
        near = [p for p in pool if p.source.grade and abs(p.source.grade - user["grade"]) <= 1]
        pool = near or pool
    return streak.pick_daily(user["id"], _today(), [p.id for p in pool])


def _todays_daily(user: dict, db: DB) -> str | None:
    """Задача дня запоминается при первом показе — весь день она одна и та же."""
    day = _today().isoformat()
    pid = db.get_daily(user["id"], day)
    if pid is None:
        pid = _daily_problem_id(user, db)
        if pid:
            db.set_daily(user["id"], day, pid)
    return pid


def _streak_info(user: dict, db: DB) -> dict:
    today = _today()
    st = db.get_streak(user["id"])
    st.refill(today)
    return {
        "count": st.visible_count(today),
        "status": st.status(today),
        "restores_left": st.restores_left,
        "restores_per_month": streak.RESTORES_PER_MONTH,
    }


def _hints_for(p: Problem, db: DB) -> Hints | None:
    if p.hints:
        return p.hints
    cached = db.cached_hints(p.id)
    return Hints.model_validate_json(cached) if cached else None


_hint_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _ensure_hints(p: Problem, user: dict, db: DB) -> Hints:
    """Подсказки задачи; если их нет — сгенерировать один раз (даже при одновременных запросах)."""
    hints = _hints_for(p, db)
    if hints is not None:
        return hints
    async with _hint_locks[p.id]:
        hints = _hints_for(p, db)
        if hints is not None:
            return hints
        rl.enforce(
            "hintgen", user["id"], 30, 3600, "Подсказки для новых задач готовятся — попробуй через час"
        )
        try:
            hints, model = await ai.generate_hints(p)
        except LLMError as exc:
            raise HTTPException(503, "ИИ-наставник сейчас перегружен, попробуй через минуту") from exc
        db.cache_hints(p.id, hints.model_dump_json(), model)
        return hints


def check_problem_answer(p: Problem, raw: str, seed: int | None = None):
    """Проверить ответ ученика: число (с единицами) или формула. seed — вариант задачи (только для чисел)."""
    if p.answer.formula is not None:
        return formula.check(p.answer.formula, p.answer.variables, raw)
    if seed is not None:
        key = make_variant(p, seed).answer
    else:
        key = AnswerKey(p.answer.value, p.answer.unit, p.answer.tolerance)
    return check_answer(key, raw)


PROOF_MAX_POINTS = 7  # как на IZhO и большинстве олимпиад с доказательствами
PROOF_SOLVED_SHARE = 0.7  # от 5 баллов из 7 задача считается решённой
