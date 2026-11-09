"""Задачи: список, карточка, проверка ответа и доказательства, подсказки, разбор."""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import ratelimit as rl
from .. import scoring
from ..bank import (
    STAGE_NAMES,
    Problem,
    load_bank,
)
from ..cloner import CloneError, find_seed, make_variant
from ..common import (
    PROOF_MAX_POINTS,
    PROOF_SOLVED_SHARE,
    SEED_MAX,
    _ensure_hints,
    _hints_for,
    _spend_ai,
    _today,
    _uid,
    check_problem_answer,
    current_user,
    figure_urls,
    get_db,
    optional_user,
    problem_points,
    require_problem,
    solve_rate,
    source_info,
    track_info,
)
from ..config import settings
from ..db import DB
from ..llm import LLMError

log = logging.getLogger("olymp")
router = APIRouter()


class CheckRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=200)
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)


class VariantRequest(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)


_tracks_cache: list = [None, None]  # [банк, треки]: храним сам банк, а не id — id может переиспользоваться


def _tracks(bank: dict[str, Problem]) -> list[dict]:
    """Треки считаются один раз на загруженный банк (load_bank закэширован)."""
    if _tracks_cache[0] is not bank:
        _tracks_cache[:] = [bank, _build_tracks(bank)]
    return _tracks_cache[1]


def _build_tracks(bank: dict[str, Problem]) -> list[dict]:
    groups: dict[str, dict] = {}
    for p in bank.values():
        g = groups.setdefault(
            p.source.track_id,
            {
                "id": p.source.track_id,
                "title": p.source.track_title(),
                "olympiad": p.source.olympiad,
                "russian": p.source.russian,
                "stage": STAGE_NAMES[p.source.stage],
                "subjects": set(),
                "years": set(),
                "grades": set(),
                "count": 0,
            },
        )
        g["subjects"].add(p.subject)
        if p.source.year:
            g["years"].add(p.source.year)
        if p.source.grade:
            g["grades"].add(p.source.grade)
        g["count"] += 1
    out = []
    for g in groups.values():
        for k in ("subjects", "years", "grades"):
            g[k] = sorted(g[k])
        out.append(g)
    out.sort(key=lambda g: (g["olympiad"], g["stage"]))
    return out


# ---------- задачи ----------
@router.get("/api/tracks")
def list_tracks() -> list[dict]:
    """Треки: олимпиада + этап (за все годы). Задачи разных треков не смешиваются."""
    return _tracks(load_bank())


@router.get("/api/topics")
def topics(track: str | None = Query(default=None)) -> list[dict]:
    seen: dict[tuple[str, str], int] = defaultdict(int)
    for p in load_bank().values():
        if track and p.source.track_id != track:
            continue
        seen[(p.subject, p.topic)] += 1
    return [{"subject": s, "topic": t, "count": n} for (s, t), n in sorted(seen.items())]


@router.get("/api/problems")
def list_problems(
    track: str | None = Query(default=None, description="Показать задачи только одного трека"),
    subject: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    user: dict | None = Depends(optional_user),
    db: DB = Depends(get_db),
) -> list[dict]:
    stats = db.problem_stats()
    prog = db.all_progress(_uid(user)) if user else {}
    out = []
    for p in load_bank().values():
        if track and p.source.track_id != track:
            continue
        if subject and p.subject != subject:
            continue
        if topic and p.topic != topic:
            continue
        pr = prog.get(p.id, {})
        solved = bool(pr.get("solved"))
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "subject": p.subject,
                "topic": p.topic,
                "track": p.source.track_id,
                "year": p.source.year,
                "points": problem_points(p, stats),
                "source": p.source.short_label(),
                "can_clone": p.can_clone,
                "solved": solved,
                "earned": pr.get("points", 0),
                "started": bool(pr.get("attempts") or pr.get("hints_used")),
                # процент решивших показываем только после решения — чтобы не пугать заранее
                "solve_rate": solve_rate(p, stats) if solved else None,
            }
        )
    out.sort(key=lambda x: (x["subject"], x["points"]))
    return out


@router.get("/api/problems/{problem_id}")
def problem_detail(
    problem_id: str,
    request: Request,
    seed: int | None = Query(default=None, ge=0, le=SEED_MAX),
    lang: str = Query(default="ru", pattern="^(ru|kk)$"),
    user: dict | None = Depends(optional_user),
    db: DB = Depends(get_db),
) -> dict:
    p = require_problem(problem_id)
    stats = db.problem_stats()
    pr = db.progress(_uid(user), p.id)
    kk = lang == "kk"  # перевод ИИ, если он есть; варианты с другими числами остаются на русском
    statement = (p.statement_kk if kk else None) or p.statement
    if seed is not None:
        _variant_guard(request)
        try:
            statement = make_variant(p, seed).statement
        except CloneError as exc:
            raise HTTPException(422, str(exc)) from exc
    hints = _hints_for(p, db)
    opened = pr["hints_used"]
    # Задачи олимпиад в тренировке заменяются аналогами (оригиналы берегут для тура), поэтому оригинал не показываем.
    replace = bool(p.can_clone and p.source.stage != "collection")
    return {
        "analogue_only": replace,
        "id": p.id,
        "title": p.title,
        "subject": p.subject,
        "topic": p.topic,
        "statement": statement,
        "original_statement": p.statement if seed is not None and not replace else None,
        "seed": seed,
        "points": problem_points(p, stats),
        "source": source_info(p),
        "track": track_info(p),
        "needs_unit": bool(p.answer.unit),
        "answer_kind": "proof" if p.is_proof else "formula" if p.answer.formula is not None else "number",
        "variables": p.answer.variables,
        "figures": figure_urls(p),
        "can_clone": p.can_clone,
        "verification": p.template.verification.model_dump() if p.template else None,
        "hints_total": len(hints.steps) if hints else 3,
        "hints_opened": hints.steps[:opened] if hints else [],
        "solution": ((p.solution_kk if kk else None) or p.solution or (hints.solution if hints else None))
        if pr["solution_viewed"]
        else None,
        "progress": {
            "attempts": pr["attempts"],
            "hints_used": pr["hints_used"],
            "solution_viewed": bool(pr["solution_viewed"]),
            "solved": bool(pr["solved"]),
            "earned": pr["points"],
        },
        "potential": scoring.reward(
            problem_points(p, stats), pr["hints_used"], bool(pr["solution_viewed"]), seed is not None
        ),
        "solve_rate": solve_rate(p, stats) if pr["solved"] else None,
    }


def _variant_guard(request: Request) -> None:
    """Каждый новый вариант — запуск решателя в отдельном процессе; не даём завалить сервер."""
    rl.enforce("variant", rl.client_ip(request), 60, 60, "Слишком много вариантов подряд — подожди минуту")


@router.post("/api/problems/{problem_id}/variant")
def new_variant(problem_id: str, request: Request, body: VariantRequest | None = None) -> dict:
    p = require_problem(problem_id)
    if not p.can_clone:
        raise HTTPException(422, "Для этой задачи варианты пока недоступны")
    _variant_guard(request)
    start = body.seed if body and body.seed else random.randint(1, 1_000_000)
    try:
        v = find_seed(p, start)
    except CloneError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "seed": v.seed,
        "statement": v.statement,
        "verification": p.template.verification.model_dump() if p.template else None,
    }


CHECKS_PER_PROBLEM = 15  # попыток ответа на одну задачу за 10 минут


@router.post("/api/problems/{problem_id}/check")
def check(
    problem_id: str, body: CheckRequest, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    if p.is_proof:
        raise HTTPException(422, "Это задача на доказательство — отправь решение целиком")
    # Перебор ответов подряд (скриптом) не должен приносить баллы рейтинга.
    rl.enforce(
        "check",
        f"{user['id']}:{p.id}",
        CHECKS_PER_PROBLEM,
        600,
        "Слишком много попыток подряд для этой задачи. Подумай ещё и попробуй через несколько минут.",
    )
    try:
        result = check_problem_answer(p, body.answer, body.seed)
    except CloneError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.log_submission(user["id"], p.id, body.seed, body.answer, result.status)

    pr = db.progress(user["id"], p.id)
    stats = db.problem_stats()
    points = problem_points(p, stats)
    earned = 0
    first_solve = False
    if result.status != "unparsable":
        pr["attempts"] += 1
    if result.correct and not pr["solved"]:
        earned = scoring.reward(points, pr["hints_used"], bool(pr["solution_viewed"]), body.seed is not None)
        pr.update(solved=1, points=earned, solved_at=time.time())
        first_solve = True
    db.save_progress(pr)
    daily_done = False
    if result.correct and first_solve and p.id == db.get_daily(user["id"], _today().isoformat()):
        st = db.get_streak(user["id"])
        st.refill(_today())
        st.complete(_today())
        db.save_streak(user["id"], st)
        daily_done = True

    stats = db.problem_stats()
    return {
        "status": result.status,
        "correct": result.correct,
        "message": result.message,
        "earned": earned,
        "first_solve": first_solve,
        "already_solved": result.correct and not first_solve,
        "daily_done": daily_done,
        "solve_rate": solve_rate(p, stats) if pr["solved"] else None,
        "total_points": sum(x["points"] for x in db.all_progress(user["id"]).values()),
    }


class ProofRequest(BaseModel):
    solution: str = Field(min_length=1, max_length=8000)


def _take_proof_check(user: dict, db: DB) -> None:
    ok = db.take_strong(
        user["id"],
        "proof:" + _today().isoformat(),
        settings.proof_per_user_daily,
        settings.proof_global_daily,
    )
    if not ok:
        raise HTTPException(
            429,
            f"Сегодня проверок доказательств больше нет (до {settings.proof_per_user_daily} в день). Приходи завтра!",
        )


@router.post("/api/problems/{problem_id}/proof")
async def check_proof(
    problem_id: str,
    body: ProofRequest,
    request: Request,
    user: dict = Depends(current_user),
    db: DB = Depends(get_db),
) -> dict:
    """Оценка доказательства «как жюри»: Sonnet сверяет решение ученика с официальным."""
    from .. import grading

    p = require_problem(problem_id)
    if not p.is_proof:
        raise HTTPException(422, "У этой задачи есть ответ — введи его в поле ответа")
    if len(body.solution.strip()) >= grading.MIN_SOLUTION_CHARS:
        _spend_ai(user, request, db)
        _take_proof_check(user, db)
    try:
        g = await grading.grade_proof(p.statement, p.solution or "", body.solution, PROOF_MAX_POINTS)
    except LLMError as exc:
        log.warning("Проверка доказательства не удалась: %s", exc)
        raise HTTPException(503, "Проверка решений сейчас недоступна, попробуй через минуту") from exc
    correct = g["points"] >= PROOF_SOLVED_SHARE * PROOF_MAX_POINTS
    db.log_submission(
        user["id"], p.id, None, f"proof:{g['points']}/{PROOF_MAX_POINTS}", "correct" if correct else "wrong"
    )
    pr = db.progress(user["id"], p.id)
    pr["attempts"] += 1
    earned, first_solve = 0, False
    if correct and not pr["solved"]:
        stats = db.problem_stats()
        earned = scoring.reward(
            problem_points(p, stats), pr["hints_used"], bool(pr["solution_viewed"]), False
        )
        pr.update(solved=1, points=earned, solved_at=time.time())
        first_solve = True
    db.save_progress(pr)
    return {
        **g,
        "correct": correct,
        "earned": earned,
        "first_solve": first_solve,
        "total_points": sum(x["points"] for x in db.all_progress(user["id"]).values()),
    }


@router.post("/api/problems/{problem_id}/hints/{level}")
async def open_hint(
    problem_id: str, level: int, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    hints = await _ensure_hints(p, user, db)
    if not 1 <= level <= len(hints.steps):
        raise HTTPException(400, "Нет такой подсказки")
    pr = db.progress(user["id"], p.id)
    if level > pr["hints_used"] + 1:
        raise HTTPException(400, "Сначала открой предыдущую подсказку")
    # после решения подсказки бесплатны, но отмечаем их, чтобы они оставались открытыми
    pr["hints_used"] = max(pr["hints_used"], level)
    db.save_progress(pr)
    stats = db.problem_stats()
    return {
        "level": level,
        "text": hints.steps[level - 1],
        "total": len(hints.steps),
        "potential": scoring.reward(
            problem_points(p, stats), pr["hints_used"], bool(pr["solution_viewed"]), False
        ),
    }


@router.post("/api/problems/{problem_id}/solution")
async def open_solution(
    problem_id: str, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    solution = p.solution or (await _ensure_hints(p, user, db)).solution
    pr = db.progress(user["id"], p.id)
    pr["solution_viewed"] = 1
    db.save_progress(pr)
    return {"solution": solution, "can_clone": p.can_clone}
