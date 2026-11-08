"""Олимпиады целиком и проверка полных решений."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .. import contests, olympiad_rules, scoring
from ..bank import (
    RUSSIAN_QUERY_WORDS,
    is_russian,
    load_bank,
)
from ..cloner import CloneError, make_variant
from ..common import (
    PROOF_SOLVED_SHARE,
    SEED_MAX,
    _spend_ai,
    _uid,
    check_problem_answer,
    current_user,
    get_db,
    optional_user,
    require_problem,
)
from ..db import DB
from ..llm import LLMError
from .problems import _take_proof_check

log = logging.getLogger("olymp")
router = APIRouter()


# ---------- проверка полных решений олимпиады «как жюри» ----------
class SolutionItem(BaseModel):
    problem_id: str = Field(max_length=200)
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)
    answer: str = Field(default="", max_length=200)
    solution: str = Field(default="", max_length=6000)
    max_points: int = Field(ge=1, le=scoring.MAX_POINTS)


class GradeRequest(BaseModel):
    items: list[SolutionItem] = Field(max_length=15)


@router.post("/api/olympiad/grade")
async def grade_olympiad(
    body: GradeRequest, request: Request, user: dict = Depends(current_user), db: DB = Depends(get_db)
) -> list[dict]:
    from .. import grading

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
    return olympiad_rules.rule_for(c.olympiad, c.stage, c.subject, c.grade, c.tour)


EQUAL_POINTS = 5  # городские этапы: задачи равноценны, а сколько баллов за каждую — в документах нет


def contest_points(c: contests.Contest) -> list[int]:
    """Баллы задач варианта: самая сложная — 10, самая простая — 3 (официальных баллов в данных нет).
    Сложность — по этапу/классу и номеру задачи в варианте (дальние задачи труднее).
    Если у олимпиады все задачи равноценны (городские Смагулова и Жаутыковская), баллы одинаковые."""
    rule = contest_rule(c)
    if rule and rule.points_per_problem:
        return [rule.points_per_problem] * len(c.problems)  # официальные баллы
    official = olympiad_rules.official_set(c.olympiad, c.stage, c.tour)
    if official and official.equal_weight:
        return [EQUAL_POINTS] * len(c.problems)
    difficulty = [scoring.base_points(p) + 0.3 * (p.source.number or i) for i, p in enumerate(c.problems, 1)]
    return scoring.scale_for_contest(difficulty)


def _completeness(c: contests.Contest) -> dict:
    """Сколько задач в официальном варианте и все ли они есть в банке (задачи одного номера — пункты одной задачи)."""
    official = olympiad_rules.official_set(c.olympiad, c.stage, c.tour)
    need = official.problems if official else None
    have = len({p.source.number or p.id for p in c.problems})
    return {
        "official_count": need,
        "complete": need is None or have == need,
        "equal_weight": bool(official and official.equal_weight),
    }


def _contest_row(c: contests.Contest, stats: dict, prog: dict) -> dict:
    pts = contest_points(c)
    return {
        **_completeness(c),
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
    pool = [
        c
        for c in contests.build_contests(load_bank()).values()
        if (not subject or c.subject == subject) and (named or not is_russian(c.olympiad))
    ]
    exact = [c for c in pool if not query or contests.matches(c.problems[0], query)]
    # Точного совпадения нет — показываем олимпиады, где совпало хотя бы одно слово («возможно, подойдут»).
    near = [] if exact else [c for c in pool if contests.matches(c.problems[0], query, partial=True)]
    rows = [{**_contest_row(c, stats, prog), "approx": not exact} for c in exact or near]
    rows.sort(key=lambda r: (r["title"].split(",")[0], -(r["year"] or 0), r["grade"] or 0))
    return rows


@router.get("/api/olympiad/available")
def olympiads_with_official_time() -> list[str]:
    complete = {
        c.olympiad
        for c in contests.build_contests(load_bank()).values()
        if contest_rule(c) and _completeness(c)["complete"]
    }
    return olympiad_rules.available_list(complete)


@router.get("/api/contests")
def list_contests(
    query: str = Query(default="", max_length=100),
    subject: str | None = None,
    user: dict | None = Depends(optional_user),
    db: DB = Depends(get_db),
) -> list[dict]:
    return _list_contests(_uid(user), db, query, subject)


@router.get("/api/contests/{contest_id}")
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
