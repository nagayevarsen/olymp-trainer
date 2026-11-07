"""Профиль ученика: серия, задача дня, прогресс, рейтинг."""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import scoring
from ..bank import (
    Problem,
    get_problem,
    load_bank,
)
from ..common import _streak_info, _today, _todays_daily, current_user, get_db, problem_points
from ..db import DB
from .problems import _tracks

log = logging.getLogger("olymp")
router = APIRouter()


@router.get("/api/daily")
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


@router.post("/api/daily/restore")
def daily_restore(user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    st = db.get_streak(user["id"])
    if not st.restore(_today()):
        raise HTTPException(400, "Серию сейчас нельзя восстановить")
    db.save_streak(user["id"], st)
    return _streak_info(user, db)


@router.get("/api/me")
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


@router.get("/api/leaderboard")
def leaderboard(db: DB = Depends(get_db)) -> list[dict]:
    return [
        {"name": r["name"], "grade": r["grade"], "points": r["points"], "solved": r["solved"]}
        for r in db.leaderboard()
    ]
