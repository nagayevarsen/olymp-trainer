"""HTTP API (FastAPI). Запуск: uvicorn app.main:app --reload (из папки backend)."""

from __future__ import annotations

import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, chat, contests, scoring
from .auth import AuthError, check_nick, check_password, hash_password, verify_password
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
    """Профиль-гость без пароля (оставлен для совместимости; прогресс живёт только в этом браузере)."""
    uid = db.create_user(body.name.strip(), body.grade)
    return {"id": uid, "name": body.name.strip(), "grade": body.grade}


def _streak(prog: dict) -> int:
    """Сколько дней подряд (включая сегодня или вчера) ученик решал хотя бы одну задачу."""
    days = {
        time.strftime("%Y-%m-%d", time.localtime(p["solved_at"])) for p in prog.values() if p.get("solved_at")
    }
    day = time.time()
    if time.strftime("%Y-%m-%d", time.localtime(day)) not in days:
        day -= 86400  # сегодня ещё не решал — серия не сгорает до конца дня
    n = 0
    while time.strftime("%Y-%m-%d", time.localtime(day)) in days:
        n += 1
        day -= 86400
    return n


# ---------- аккаунт: ник + пароль, без почты и телефона ----------
class Register(BaseModel):
    nick: str = Field(max_length=40)
    password: str = Field(max_length=200)
    grade: int | None = Field(default=None, ge=1, le=12)
    accept_terms: bool = False


class Login(BaseModel):
    nick: str = Field(max_length=40)
    password: str = Field(max_length=200)


def _account_fields(nick: str, password: str) -> tuple[str, str]:
    try:
        nick = check_nick(nick)
        check_password(password)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return nick, hash_password(password)


@app.get("/api/nick-available")
def nick_available(nick: str, db: DB = Depends(get_db)) -> dict:
    try:
        nick = check_nick(nick)
    except AuthError as exc:
        return {"available": False, "reason": str(exc)}
    taken = db.nick_taken(nick)
    return {"available": not taken, "reason": "Такой ник уже занят" if taken else None}


@app.post("/api/register")
def register(body: Register, db: DB = Depends(get_db)) -> dict:
    if not body.accept_terms:
        raise HTTPException(400, "Нужно согласиться с условиями использования")
    nick, pass_hash = _account_fields(body.nick, body.password)
    uid = db.create_account(nick, pass_hash, body.grade)
    if uid is None:
        raise HTTPException(409, "Такой ник уже занят")
    return {"id": uid, "name": nick, "grade": body.grade}


@app.post("/api/login")
def login(body: Login, db: DB = Depends(get_db)) -> dict:
    user = db.user_by_nick(body.nick.strip())
    if not user or not verify_password(body.password, user["pass_hash"]):
        time.sleep(0.5)  # замедляем подбор пароля
        raise HTTPException(401, "Неверный ник или пароль")
    return {"id": user["id"], "name": user["name"], "grade": user["grade"]}


@app.post("/api/me/account")
def attach_account(body: Login, user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    """Гость задаёт ник и пароль — прогресс сохраняется и становится доступен с других устройств."""
    if user.get("pass_hash"):
        raise HTTPException(400, "У профиля уже есть ник и пароль")
    nick, pass_hash = _account_fields(body.nick, body.password)
    if not db.attach_account(user["id"], nick, pass_hash):
        raise HTTPException(409, "Такой ник уже занят")
    return {"id": user["id"], "name": nick}


@app.delete("/api/me")
def delete_me(user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    db.delete_user(user["id"])
    return {"deleted": True}


# ---------- чат с ИИ-помощником ----------
class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=chat.MAX_MESSAGE * 2)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(max_length=100)
    problem_id: str | None = None
    mode: Literal["training", "olympiad"] = "training"


@app.post("/api/chat")
async def chat_reply(body: ChatRequest, user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    try:
        history = chat.clean_history([m.model_dump() for m in body.messages])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    used = db.count_chat_message(user["id"], time.strftime("%Y-%m-%d"))
    if used > chat.DAILY_LIMIT:
        raise HTTPException(
            429, f"На сегодня лимит {chat.DAILY_LIMIT} сообщений помощнику. Возвращайся завтра!"
        )
    prog = db.all_progress(user["id"])
    level = chat.Level(
        grade=user["grade"],
        solved=sum(p["solved"] for p in prog.values()),
        attempted=len(prog),
        best_points=max((p["points"] for p in prog.values() if p["solved"]), default=0),
    )
    tools = chat.ChatTools(
        search=lambda **kw: _search_bank(user, db, **kw),
        contests=lambda **kw: [
            r
            for r in _list_contests(user["id"], db, **kw)
            if not user["grade"] or not r["grade"] or abs(r["grade"] - user["grade"]) <= 1
        ][:6],
    )
    problem = None
    if body.problem_id and (p := get_problem(body.problem_id)):
        problem = {"source": p.source.label(), "topic": p.topic, "statement": p.statement}
    try:
        text, code_runs, cards = await chat.reply(
            history, level, problem, tools, olympiad=body.mode == "olympiad"
        )
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"reply": text, "code_runs": code_runs, "cards": cards, "left": max(0, chat.DAILY_LIMIT - used)}


def _search_bank(user: dict, db: DB, **kw) -> list[dict]:
    stats = db.problem_stats()
    solved = {pid for pid, pr in db.all_progress(user["id"]).items() if pr["solved"]}

    def points(p):
        return problem_points(p, stats)

    found = contests.search_problems(load_bank(), points, solved, grade=user["grade"], **kw)
    if not found and kw.get("query") and (kw.get("min_points") or kw.get("max_points")):
        # Названная олимпиада важнее уровня: берём её самые лёгкие задачи.
        kw = {k: v for k, v in kw.items() if k not in ("min_points", "max_points")}
        found = contests.search_problems(load_bank(), points, solved, grade=user["grade"], **kw)
    return found


# ---------- полные олимпиады: все задачи банка одной олимпиады, года и класса ----------
def _contest_row(c: contests.Contest, stats: dict, prog: dict) -> dict:
    pts = [problem_points(p, stats) for p in c.problems]
    return {
        "id": c.id,
        "title": c.title,
        "subject": c.subject,
        "year": c.year,
        "grade": c.grade,
        "count": len(c.problems),
        "total_points": sum(pts),
        "solved": sum(1 for p in c.problems if prog.get(p.id, {}).get("solved")),
        "earned": sum(prog.get(p.id, {}).get("points", 0) for p in c.problems),
    }


def _list_contests(uid: str, db: DB, query: str = "", subject: str | None = None) -> list[dict]:
    stats = db.problem_stats()
    prog = db.all_progress(uid) if uid else {}
    rows = [
        _contest_row(c, stats, prog)
        for c in contests.build_contests(load_bank()).values()
        if (not subject or c.subject == subject) and (not query or contests.matches(c.problems[0], query))
    ]
    rows.sort(key=lambda r: (r["title"].split(",")[0], -(r["year"] or 0), r["grade"] or 0))
    return rows


@app.get("/api/contests")
def list_contests(
    query: str = "", subject: str | None = None, x_user_id: str = Header(default=""), db: DB = Depends(get_db)
) -> list[dict]:
    return _list_contests(x_user_id, db, query, subject)


@app.get("/api/contests/{contest_id}")
def contest_detail(contest_id: str, x_user_id: str = Header(default=""), db: DB = Depends(get_db)) -> dict:
    c = contests.build_contests(load_bank()).get(contest_id)
    if not c:
        raise HTTPException(404, "Олимпиада не найдена")
    stats = db.problem_stats()
    prog = db.all_progress(x_user_id) if x_user_id else {}
    problems = []
    for i, p in enumerate(c.problems, 1):
        pr = prog.get(p.id, {})
        problems.append(
            {
                "n": i,
                "id": p.id,
                "title": p.title,
                "topic": p.topic,
                "points": problem_points(p, stats),
                "solved": bool(pr.get("solved")),
                "earned": pr.get("points", 0),
                "started": bool(pr.get("attempts") or pr.get("hints_used")),
                "can_clone": p.can_clone,
            }
        )
    return {**_contest_row(c, stats, prog), "stage": c.stage, "problems": problems}


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
        "has_account": bool(user.get("pass_hash")),
        "streak": _streak(prog),
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
