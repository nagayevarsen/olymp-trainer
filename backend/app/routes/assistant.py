"""ИИ-помощник: чат, подбор задач, микс."""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import chat, contests
from ..bank import (
    Problem,
    figures_dir,
    get_problem,
    load_bank,
)
from ..common import _hints_for, _spend_ai, current_user, get_db, problem_points
from ..config import settings
from ..db import DB
from ..llm import LLMError
from .olympiads import _list_contests

log = logging.getLogger("olymp")
router = APIRouter()


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
    lang: Literal["ru", "kk"] = "ru"


@router.post("/api/chat")
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
        if db.progress(user["id"], p.id)["solution_viewed"]:  # разбор ученик уже видел — его можно обсуждать
            hints = _hints_for(p, db)
            problem["solution"] = p.solution or (hints.solution if hints else "")
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
            lang=body.lang,
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


@router.get("/api/mix")
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
