"""HTTP API (FastAPI). Запуск: uvicorn app.main:app --reload (из папки backend)."""

from __future__ import annotations

import random
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, scoring
from .bank import STAGE_NAMES, Hints, Problem, get_problem, load_bank
from .checker import AnswerKey, check_answer
from .cloner import CloneError, find_seed, make_variant
from .config import settings
from .db import DB
from .llm import LLMError

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def current_user(x_user_id: str = Header(default=""), db: DB = Depends(get_db)) -> dict:
    user = db.get_user(x_user_id) if x_user_id else None
    if not user:
        raise HTTPException(401, "Нужно войти: создайте профиль")
    return dict(user)


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


def source_info(p: Problem) -> dict:
    return {
        "label": p.source.label(),
        "stage": STAGE_NAMES[p.source.stage],
        "url": p.source.url,
    }


# ---------- схемы запросов ----------
class NewUser(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    grade: int | None = Field(default=None, ge=1, le=12)


class CheckRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=200)
    seed: int | None = None


class VariantRequest(BaseModel):
    seed: int | None = None


# ---------- пользователи ----------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "problems": len(load_bank()), "app": settings.app_name}


@app.post("/api/users")
def create_user(body: NewUser, db: DB = Depends(get_db)) -> dict:
    uid = db.create_user(body.name.strip(), body.grade)
    return {"id": uid, "name": body.name.strip(), "grade": body.grade}


@app.get("/api/me")
def me(
    track: str | None = Query(default=None, description="Трек, из которого рекомендовать задачи"),
    user: dict = Depends(current_user),
    db: DB = Depends(get_db),
) -> dict:
    bank = load_bank()
    stats = db.problem_stats()
    prog = db.all_progress(user["id"])
    if track is None or not any(p.source.track_id == track for p in bank.values()):
        track = _main_track(bank, prog)

    topics: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "solved": 0, "tried": 0, "points": 0, "hints": 0}
    )
    for p in bank.values():
        key = f"{p.subject}:{p.topic}"
        t = topics[key]
        t["subject"], t["topic"] = p.subject, p.topic
        t["total"] += 1
        pr = prog.get(p.id)
        if pr:
            t["solved"] += pr["solved"]
            t["tried"] += 1 if (pr["attempts"] or pr["hints_used"] or pr["solved"]) else 0
            t["points"] += pr["points"]
            t["hints"] += pr["hints_used"]

    weak = [
        t["topic"]
        for t in topics.values()
        if t["tried"] >= 1 and (t["solved"] / t["tried"] < 0.5 or t["hints"] / t["tried"] >= 2)
    ]

    solved_points = [
        problem_points(bank[pid], stats) for pid, pr in prog.items() if pr["solved"] and pid in bank
    ]
    target = (sum(solved_points) / len(solved_points) + 100) if solved_points else 200
    # рекомендуем только из одного трека: олимпиады и этапы не смешиваем
    unsolved = [
        p for p in bank.values() if p.source.track_id == track and not prog.get(p.id, {}).get("solved")
    ]
    # сначала задачи из слабых тем, затем ближайшие по баллам к уровню ученика
    unsolved.sort(key=lambda p: (p.topic not in weak, abs(problem_points(p, stats) - target)))
    recommended = [
        {
            "id": p.id,
            "title": p.title,
            "topic": p.topic,
            "subject": p.subject,
            "points": problem_points(p, stats),
        }
        for p in unsolved[:3]
    ]

    board = db.leaderboard(limit=1000)
    rank = next((i + 1 for i, r in enumerate(board) if r["id"] == user["id"]), None)
    return {
        "id": user["id"],
        "name": user["name"],
        "grade": user["grade"],
        "points": sum(pr["points"] for pr in prog.values()),
        "solved": sum(pr["solved"] for pr in prog.values()),
        "rank": rank,
        "users_total": len(board),
        "topics": sorted(topics.values(), key=lambda t: (t["subject"], t["topic"])),
        "weak_topics": weak,
        "track": track,
        "recommended": recommended,
    }


def _main_track(bank: dict[str, Problem], prog: dict[str, dict]) -> str | None:
    """Трек, в котором ученик больше всего занимался (или первый по списку)."""
    activity: dict[str, int] = defaultdict(int)
    for pid in prog:
        if pid in bank:
            activity[bank[pid].source.track_id] += 1
    if activity:
        return max(activity, key=lambda t: activity[t])
    tracks = _tracks(bank)
    return tracks[0]["id"] if tracks else None


def _tracks(bank: dict[str, Problem]) -> list[dict]:
    groups: dict[str, dict] = {}
    for p in bank.values():
        g = groups.setdefault(
            p.source.track_id,
            {
                "id": p.source.track_id,
                "title": p.source.track_title(),
                "olympiad": p.source.olympiad,
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


@app.get("/api/leaderboard")
def leaderboard(db: DB = Depends(get_db)) -> list[dict]:
    return [
        {"name": r["name"], "grade": r["grade"], "points": r["points"], "solved": r["solved"]}
        for r in db.leaderboard()
    ]


# ---------- задачи ----------
@app.get("/api/tracks")
def list_tracks() -> list[dict]:
    """Треки: олимпиада + этап (за все годы). Задачи разных треков не смешиваются."""
    return _tracks(load_bank())


@app.get("/api/topics")
def topics(track: str | None = Query(default=None)) -> list[dict]:
    seen: dict[tuple[str, str], int] = defaultdict(int)
    for p in load_bank().values():
        if track and p.source.track_id != track:
            continue
        seen[(p.subject, p.topic)] += 1
    return [{"subject": s, "topic": t, "count": n} for (s, t), n in sorted(seen.items())]


@app.get("/api/problems")
def list_problems(
    track: str | None = Query(default=None, description="Показать задачи только одного трека"),
    subject: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    x_user_id: str = Header(default=""),
    db: DB = Depends(get_db),
) -> list[dict]:
    stats = db.problem_stats()
    prog = db.all_progress(x_user_id) if x_user_id else {}
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


def _hints_for(p: Problem, db: DB) -> Hints | None:
    if p.hints:
        return p.hints
    cached = db.cached_hints(p.id)
    return Hints.model_validate_json(cached) if cached else None


@app.get("/api/problems/{problem_id}")
def problem_detail(
    problem_id: str,
    seed: int | None = None,
    x_user_id: str = Header(default=""),
    db: DB = Depends(get_db),
) -> dict:
    p = require_problem(problem_id)
    stats = db.problem_stats()
    pr = db.progress(x_user_id, p.id) if x_user_id else db.progress("", p.id)
    statement = p.statement
    if seed is not None:
        try:
            statement = make_variant(p, seed).statement
        except CloneError as exc:
            raise HTTPException(422, str(exc)) from exc
    hints = _hints_for(p, db)
    opened = pr["hints_used"]
    return {
        "id": p.id,
        "title": p.title,
        "subject": p.subject,
        "topic": p.topic,
        "statement": statement,
        "original_statement": p.statement if seed is not None else None,
        "seed": seed,
        "points": problem_points(p, stats),
        "source": source_info(p),
        "track": track_info(p),
        "needs_unit": bool(p.answer.unit),
        "can_clone": p.can_clone,
        "verification": p.template.verification.model_dump() if p.template else None,
        "hints_total": len(hints.steps) if hints else 3,
        "hints_opened": hints.steps[:opened] if hints else [],
        "solution": (p.solution or (hints.solution if hints else None)) if pr["solution_viewed"] else None,
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


@app.post("/api/problems/{problem_id}/variant")
def new_variant(problem_id: str, body: VariantRequest | None = None) -> dict:
    p = require_problem(problem_id)
    if not p.can_clone:
        raise HTTPException(422, "Для этой задачи варианты пока недоступны")
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


@app.post("/api/problems/{problem_id}/check")
def check(
    problem_id: str, body: CheckRequest, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    if body.seed is not None:
        try:
            key = make_variant(p, body.seed).answer
        except CloneError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        key = AnswerKey(p.answer.value, p.answer.unit, p.answer.tolerance)

    result = check_answer(key, body.answer)
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

    stats = db.problem_stats()
    return {
        "status": result.status,
        "correct": result.correct,
        "message": result.message,
        "earned": earned,
        "first_solve": first_solve,
        "already_solved": result.correct and not first_solve,
        "solve_rate": solve_rate(p, stats) if pr["solved"] else None,
        "total_points": sum(x["points"] for x in db.all_progress(user["id"]).values()),
    }


@app.post("/api/problems/{problem_id}/hints/{level}")
async def open_hint(
    problem_id: str, level: int, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    hints = _hints_for(p, db)
    if hints is None:
        try:
            hints, model = await ai.generate_hints(p)
        except LLMError as exc:
            raise HTTPException(503, "ИИ-наставник сейчас перегружен, попробуй через минуту") from exc
        db.cache_hints(p.id, hints.model_dump_json(), model)
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


@app.post("/api/problems/{problem_id}/solution")
async def open_solution(
    problem_id: str, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    solution = p.solution
    if not solution:
        hints = _hints_for(p, db)
        if hints is None:
            try:
                hints, model = await ai.generate_hints(p)
            except LLMError as exc:
                raise HTTPException(503, "ИИ-наставник сейчас перегружен, попробуй через минуту") from exc
            db.cache_hints(p.id, hints.model_dump_json(), model)
        solution = hints.solution
    pr = db.progress(user["id"], p.id)
    pr["solution_viewed"] = 1
    db.save_progress(pr)
    return {"solution": solution, "can_clone": p.can_clone}


# ---------- фронтенд (собранный) ----------
_dist = Path(settings.frontend_dist)
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = _dist / path
        if path and file.is_file() and _dist in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(_dist / "index.html")
