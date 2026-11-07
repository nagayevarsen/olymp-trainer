"""HTTP API (FastAPI). Запуск: uvicorn app.main:app --reload (из папки backend)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, chat, contests, formula, olympiad_rules, scoring, streak
from . import ratelimit as rl
from .auth import AuthError, check_nick, check_password, hash_password, verify_password
from .bank import (
    RUSSIAN_QUERY_WORDS,
    STAGE_NAMES,
    Hints,
    Problem,
    figures_dir,
    get_problem,
    is_russian,
    load_bank,
)
from .checker import AnswerKey, check_answer
from .cloner import CloneError, find_seed, make_variant
from .config import settings
from .db import DB
from .llm import LLMError

log = logging.getLogger("olymp")
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

MAX_BODY_BYTES = 1_000_000
SEED_MAX = 2**31 - 1


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Слишком большие запросы отклоняем сразу; ответам — стандартные заголовки безопасности."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Слишком большой запрос"}, status_code=413)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    path = request.url.path
    if path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/assets/"):
        # В именах собранных файлов есть хэш содержимого — браузер может хранить их хоть год.
        resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    else:
        # index.html и sw.js должны обновляться сразу после выкладки новой версии.
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


# Сжатие ответов: список задач ~300 КБ JSON сжимается в несколько раз. Добавляется после
# middleware заголовков, поэтому оборачивает его снаружи и сжимает уже готовый ответ.
app.add_middleware(GZipMiddleware, minimum_size=1000)


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


# ---------- схемы запросов ----------
class NewUser(BaseModel):
    # Имя гостя видно в рейтинге: только буквы, цифры, пробел, точка, дефис.
    name: str = Field(min_length=1, max_length=20, pattern=r"^[\w .\-]+$")
    grade: int | None = Field(default=None, ge=1, le=12)


class CheckRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=200)
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)


class VariantRequest(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)


# ---------- пользователи ----------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "problems": len(load_bank()), "app": settings.app_name}


@app.post("/api/users")
def create_user(body: NewUser, request: Request, db: DB = Depends(get_db)) -> dict:
    """Профиль-гость без пароля (оставлен для совместимости; прогресс живёт только в этом браузере)."""
    _signup_guard(request)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Пустое имя")
    uid = db.create_user(name, body.grade)
    return {"id": uid, "name": name, "grade": body.grade, "token": db.create_session(uid)}


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


@app.get("/api/daily")
def daily(user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    pid = _todays_daily(user, db)
    p = get_problem(pid) if pid else None
    stats = db.problem_stats()
    return {
        "problem": (
            {
                "id": p.id,
                "title": p.title,
                "topic": p.topic,
                "points": problem_points(p, stats),
                "source": p.source.label(),
            }
            if p
            else None
        ),
        "streak": _streak_info(user, db),
    }


@app.post("/api/daily/restore")
def daily_restore(user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    st = db.get_streak(user["id"])
    if not st.restore(_today()):
        raise HTTPException(400, "Серию сейчас нельзя восстановить")
    db.save_streak(user["id"], st)
    return _streak_info(user, db)


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
        check_password(password, nick)
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
def register(body: Register, request: Request, db: DB = Depends(get_db)) -> dict:
    if not body.accept_terms:
        raise HTTPException(400, "Нужно согласиться с условиями использования")
    nick, pass_hash = _account_fields(body.nick, body.password)
    _signup_guard(request)
    uid = db.create_account(nick, pass_hash, body.grade)
    if uid is None:
        raise HTTPException(409, "Такой ник уже занят")
    return {"id": uid, "name": nick, "grade": body.grade, "token": db.create_session(uid)}


LOGIN_FAILS_PER_NICK = 10  # за 15 минут
LOGIN_FAILS_PER_IP = 50


@app.post("/api/login")
async def login(body: Login, request: Request, db: DB = Depends(get_db)) -> dict:
    nick_key, ip = body.nick.strip().lower(), rl.client_ip(request)
    if not (
        rl.allow("login-nick", nick_key, LOGIN_FAILS_PER_NICK, 900, count=False)
        and rl.allow("login-ip", ip, LOGIN_FAILS_PER_IP, 900, count=False)
    ):
        raise HTTPException(429, "Слишком много неудачных попыток входа. Подожди 15 минут.")
    user = db.user_by_nick(body.nick.strip())
    ok = bool(user) and await asyncio.to_thread(verify_password, body.password, user["pass_hash"])
    if not ok:
        rl.hit("login-nick", nick_key)
        rl.hit("login-ip", ip)
        await asyncio.sleep(0.5)  # замедляем подбор пароля, не блокируя сервер
        raise HTTPException(401, "Неверный ник или пароль")
    return {
        "id": user["id"],
        "name": user["name"],
        "grade": user["grade"],
        "token": db.create_session(user["id"]),
    }


@app.post("/api/logout")
def logout(authorization: str = Header(default=""), db: DB = Depends(get_db)) -> dict:
    if token := _bearer(authorization):
        db.delete_session(token)
    return {"ok": True}


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
    role: Literal["user", "assistant"]
    content: str = Field(max_length=chat.MAX_MESSAGE * 2)


class ChatAttachment(BaseModel):
    data: str = Field(max_length=5_600_000, description="Файл в base64 (фото или PDF, до 4 МБ)")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(max_length=100)
    attachments: list[ChatAttachment] = Field(default=[], max_length=chat.MAX_UPLOADS)
    problem_id: str | None = Field(default=None, max_length=200)
    mode: Literal["training", "olympiad"] = "training"


@app.post("/api/chat")
async def chat_reply(
    body: ChatRequest, request: Request, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    try:
        history = chat.clean_history([m.model_dump() for m in body.messages])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        uploads = chat.upload_blocks([a.model_dump() for a in body.attachments])
    except chat.UploadError as exc:
        raise HTTPException(400, str(exc)) from exc
    if uploads and body.mode == "olympiad":
        raise HTTPException(400, "Во время олимпиады файлы прикреплять нельзя")
    used = _spend_ai(user, request, db)
    prog = db.all_progress(user["id"])
    level = chat.Level(
        grade=user["grade"],
        solved=sum(p["solved"] for p in prog.values()),
        attempted=len(prog),
        best_points=max((p["points"] for p in prog.values() if p["solved"]), default=0),
    )
    tools = chat.ChatTools(
        mix=lambda **kw: _mix(
            user,
            db,
            kw.get("subject"),
            kw.get("kind") == "proof",
            min(max(int(kw.get("count") or 6), 2), MIX_MAX),
        ),
        search=lambda **kw: _search_bank(user, db, **kw),
        contests=lambda **kw: [
            r
            for r in _list_contests(user["id"], db, **kw)
            if not user["grade"] or not r["grade"] or abs(r["grade"] - user["grade"]) <= 1
        ][:6],
    )
    problem, figures = None, []
    if body.problem_id and (p := get_problem(body.problem_id)):
        problem = {"source": p.source.label(), "topic": p.topic, "statement": p.statement}
        figures = [figures_dir() / f for f in p.figures]
    strong_used: list[bool] = []

    def take_strong() -> bool:
        """Разрешить один запрос к Sonnet, если не исчерпаны личный и общий дневные лимиты."""
        ok = db.take_strong(
            user["id"],
            time.strftime("%Y-%m-%d"),
            settings.strong_per_user_daily,
            settings.strong_global_daily,
        )
        if ok:
            strong_used.append(True)
        return ok

    try:
        text, code_runs, cards = await chat.reply(
            history,
            level,
            problem,
            tools,
            olympiad=body.mode == "olympiad",
            strong=take_strong,
            figures=figures,
            uploads=uploads,
        )
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "reply": text,
        "code_runs": code_runs,
        "cards": cards,
        "left": max(0, chat.DAILY_LIMIT - used),
        "strong": bool(strong_used),
    }


MIX_MAX = 10


def _mix(user: dict, db: DB, subject: str | None, proof: bool, n: int) -> list[dict]:
    """Микс: нерешённые задачи разных олимпиад одного типа — все на доказательство или все с ответом."""
    stats = db.problem_stats()
    solved = {pid for pid, pr in db.all_progress(user["id"]).items() if pr["solved"]}
    by_olympiad: dict[str, list[Problem]] = defaultdict(list)
    for p in load_bank().values():
        if (
            p.id in solved
            or p.source.olympiad.startswith("Демо")
            or (subject and p.subject != subject)
            or p.is_proof != proof
            or (user["grade"] and p.source.grade and abs(p.source.grade - user["grade"]) > 1)
        ):
            continue
        by_olympiad[p.source.olympiad].append(p)
    queues = list(by_olympiad.values())
    for q in queues:
        random.shuffle(q)
    random.shuffle(queues)
    picked: list[Problem] = []
    while queues and len(picked) < n:  # по кругу: по одной задаче из каждой олимпиады
        for q in queues:
            if q and len(picked) < n:
                picked.append(q.pop())
        queues = [q for q in queues if q]
    picked.sort(key=lambda p: problem_points(p, stats))
    return [
        {
            "id": p.id,
            "title": p.title,
            "source": p.source.label(),
            "topic": p.topic,
            "points": problem_points(p, stats),
            "subject": p.subject,
        }
        for p in picked
    ]


@app.get("/api/mix")
def mix(
    subject: Literal["math", "physics"] | None = None,
    kind: Literal["answer", "proof"] = "answer",
    n: int = Query(default=6, ge=2, le=MIX_MAX),
    user: dict = Depends(current_user),
    db: DB = Depends(get_db),
) -> list[dict]:
    return _mix(user, db, subject, kind == "proof", n)


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


# ---------- проверка полных решений олимпиады «как жюри» ----------
class SolutionItem(BaseModel):
    problem_id: str = Field(max_length=200)
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)
    answer: str = Field(default="", max_length=200)
    solution: str = Field(default="", max_length=6000)
    max_points: int = Field(ge=1, le=scoring.MAX_POINTS)


class GradeRequest(BaseModel):
    items: list[SolutionItem] = Field(max_length=15)


@app.post("/api/olympiad/grade")
async def grade_olympiad(
    body: GradeRequest, request: Request, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> list[dict]:
    from . import grading

    problems = [require_problem(it.problem_id) for it in body.items]
    # Каждая задача с решением — отдельный запрос к ИИ: считаем их в общий дневной лимит.
    _spend_ai(user, request, db, n=sum(1 for it in body.items if it.solution.strip() or it.answer.strip()))
    out = []
    for it, p in zip(body.items, problems):
        if p.is_proof:
            try:
                if it.solution.strip():
                    _take_proof_check(user, db)
                g = await grading.grade_proof(p.statement, p.solution or "", it.solution, it.max_points)
            except LLMError as exc:
                log.warning("Проверка доказательства не удалась: %s", exc)
                raise HTTPException(503, "Проверка решений сейчас недоступна, попробуй через минуту") from exc
            ok = g["points"] >= PROOF_SOLVED_SHARE * it.max_points
            out.append({"problem_id": p.id, "answer_correct": ok, **g})
            continue
        statement, value, unit = p.statement, p.answer.formula or p.answer.value, p.answer.unit
        seed = it.seed if it.seed is not None and p.can_clone else None
        if seed is not None:
            try:
                v = make_variant(p, seed)
                statement, value, unit = v.statement, v.answer.value, v.answer.unit
            except CloneError:
                seed = None
        correct = bool(it.answer.strip()) and check_problem_answer(p, it.answer, seed).correct
        try:
            g = await grading.grade(
                statement, value, unit, p.solution, it.solution, it.answer, correct, it.max_points
            )
        except LLMError as exc:
            # Подробности (модели, куски ответа) ученику не показываем — только в лог сервера.
            log.warning("Проверка решения не удалась: %s", exc)
            raise HTTPException(503, "Проверка решений сейчас недоступна, попробуй через минуту") from exc
        out.append({"problem_id": p.id, "answer_correct": correct, **g})
    return out


# ---------- полные олимпиады: все задачи банка одной олимпиады, года и класса ----------
def contest_rule(c: contests.Contest) -> olympiad_rules.Rule | None:
    return olympiad_rules.rule_for(c.olympiad, c.stage, c.subject, c.grade)


def contest_points(c: contests.Contest) -> list[int]:
    """Баллы задач варианта: самая сложная — 10, самая простая — 3 (официальных баллов в данных нет).
    Сложность — по этапу/классу и номеру задачи в варианте (дальние задачи труднее)."""
    rule = contest_rule(c)
    if rule and rule.points_per_problem:
        return [rule.points_per_problem] * len(c.problems)  # официальные баллы
    difficulty = [scoring.base_points(p) + 0.3 * (p.source.number or i) for i, p in enumerate(c.problems, 1)]
    return scoring.scale_for_contest(difficulty)


def _contest_row(c: contests.Contest, stats: dict, prog: dict) -> dict:
    pts = contest_points(c)
    return {
        "id": c.id,
        "title": c.title,
        "subject": c.subject,
        "year": c.year,
        "grade": c.grade,
        "count": len(c.problems),
        "russian": is_russian(c.olympiad),
        "total_points": sum(pts),
        "solved": sum(1 for p in c.problems if prog.get(p.id, {}).get("solved")),
        "earned": sum(prog.get(p.id, {}).get("points", 0) for p in c.problems),
        **_rule_info(contest_rule(c)),
    }


def _rule_info(rule: olympiad_rules.Rule | None) -> dict:
    """Официальная длительность тура (если известна) и источник. Без неё олимпиада на время недоступна."""
    if not rule:
        return {"duration_min": None, "duration_source": None, "official_points": False}
    return {
        "duration_min": rule.minutes,
        "duration_source": {"name": rule.source_name, "url": rule.source_url},
        "official_points": bool(rule.points_per_problem),
    }


def _list_contests(uid: str, db: DB, query: str = "", subject: str | None = None) -> list[dict]:
    stats = db.problem_stats()
    prog = db.all_progress(uid) if uid else {}
    # Российские олимпиады (очные этапы в России) показываем, только если ученик назвал их сам.
    named = any(w in query.lower() for w in RUSSIAN_QUERY_WORDS)
    rows = [
        _contest_row(c, stats, prog)
        for c in contests.build_contests(load_bank()).values()
        if (not subject or c.subject == subject)
        and (not query or contests.matches(c.problems[0], query))
        and (named or not is_russian(c.olympiad))
    ]
    rows.sort(key=lambda r: (r["title"].split(",")[0], -(r["year"] or 0), r["grade"] or 0))
    return rows


@app.get("/api/olympiad/available")
def olympiads_with_official_time() -> list[str]:
    return olympiad_rules.available_list()


@app.get("/api/contests")
def list_contests(
    query: str = Query(default="", max_length=100),
    subject: str | None = None,
    user: dict | None = Depends(optional_user),
    db: DB = Depends(get_db),
) -> list[dict]:
    return _list_contests(_uid(user), db, query, subject)


@app.get("/api/contests/{contest_id}")
def contest_detail(
    contest_id: str, user: dict | None = Depends(optional_user), db: DB = Depends(get_db)
) -> dict:
    c = contests.build_contests(load_bank()).get(contest_id)
    if not c:
        raise HTTPException(404, "Олимпиада не найдена")
    stats = db.problem_stats()
    prog = db.all_progress(_uid(user)) if user else {}
    problems = []
    for i, (p, pts) in enumerate(zip(c.problems, contest_points(c)), 1):
        pr = prog.get(p.id, {})
        problems.append(
            {
                "n": i,
                "id": p.id,
                "title": p.title,
                "topic": p.topic,
                "points": pts,
                "source": p.source.label(),
                "url": p.source.url,
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
        lambda: {"total": 0, "solved": 0, "tried": 0, "points": 0, "hints": 0, "possible": 0}
    )
    for p in bank.values():
        key = f"{p.subject}:{p.topic}"
        t = topics[key]
        t["subject"], t["topic"] = p.subject, p.topic
        t["total"] += 1
        pr = prog.get(p.id)
        if pr:
            t["solved"] += pr["solved"]
            tried = bool(pr["attempts"] or pr["hints_used"] or pr["solved"])
            t["tried"] += tried
            t["points"] += pr["points"]
            t["hints"] += pr["hints_used"]
            if tried:
                t["possible"] += problem_points(p, stats)

    # Уровень — взвешенный процент (scoring.mastery): сложная задача весит больше лёгкой.
    for t in topics.values():
        t["mastery"] = scoring.mastery([t["points"]], [t.pop("possible")])
    weak = [t["topic"] for t in topics.values() if t["mastery"] is not None and t["mastery"] < 50]

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
        "streak": _streak_info(user, db)["count"],
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


@app.get("/api/problems/{problem_id}")
def problem_detail(
    problem_id: str,
    request: Request,
    seed: int | None = Query(default=None, ge=0, le=SEED_MAX),
    user: dict | None = Depends(optional_user),
    db: DB = Depends(get_db),
) -> dict:
    p = require_problem(problem_id)
    stats = db.problem_stats()
    pr = db.progress(_uid(user), p.id)
    statement = p.statement
    if seed is not None:
        _variant_guard(request)
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
        "answer_kind": "proof" if p.is_proof else "formula" if p.answer.formula is not None else "number",
        "variables": p.answer.variables,
        "figures": figure_urls(p),
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


def _variant_guard(request: Request) -> None:
    """Каждый новый вариант — запуск решателя в отдельном процессе; не даём завалить сервер."""
    rl.enforce("variant", rl.client_ip(request), 60, 60, "Слишком много вариантов подряд — подожди минуту")


@app.post("/api/problems/{problem_id}/variant")
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


def check_problem_answer(p: Problem, raw: str, seed: int | None = None):
    """Проверить ответ ученика: число (с единицами) или формула. seed — вариант задачи (только для чисел)."""
    if p.answer.formula is not None:
        return formula.check(p.answer.formula, p.answer.variables, raw)
    if seed is not None:
        key = make_variant(p, seed).answer
    else:
        key = AnswerKey(p.answer.value, p.answer.unit, p.answer.tolerance)
    return check_answer(key, raw)


@app.post("/api/problems/{problem_id}/check")
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


PROOF_MAX_POINTS = 7  # как на IZhO и большинстве олимпиад с доказательствами
PROOF_SOLVED_SHARE = 0.7  # от 5 баллов из 7 задача считается решённой


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


@app.post("/api/problems/{problem_id}/proof")
async def check_proof(
    problem_id: str,
    body: ProofRequest,
    request: Request,
    user: dict = Depends(current_user),
    db: DB = Depends(get_db),
) -> dict:
    """Оценка доказательства «как жюри»: Sonnet сверяет решение ученика с официальным."""
    from . import grading

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


@app.post("/api/problems/{problem_id}/hints/{level}")
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


@app.post("/api/problems/{problem_id}/solution")
async def open_solution(
    problem_id: str, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> dict:
    p = require_problem(problem_id)
    solution = p.solution or (await _ensure_hints(p, user, db)).solution
    pr = db.progress(user["id"], p.id)
    pr["solution_viewed"] = 1
    db.save_progress(pr)
    return {"solution": solution, "can_clone": p.can_clone}


# ---------- фронтенд (собранный) ----------
_figures = figures_dir()
_figures.mkdir(parents=True, exist_ok=True)
app.mount("/figures", StaticFiles(directory=_figures), name="figures")

_dist = Path(settings.frontend_dist).resolve()
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Нет такого адреса API")
        file = (_dist / path).resolve()
        if path and _dist in file.parents and file.is_file():
            return FileResponse(file)
        return FileResponse(_dist / "index.html")
