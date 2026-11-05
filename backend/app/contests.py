"""Поиск задач в банке и «полные олимпиады».

Полная олимпиада — все задачи банка одной олимпиады и этапа за один год и один класс
(например «Всесибирская — заключительный этап, 2024, 9 класс»), с баллами за каждую задачу.
Этим пользуются и раздел «Олимпиады», и чат-помощник (инструменты search_problems / list_contests).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .bank import Problem

MIN_CONTEST_PROBLEMS = 2


def _norm(s: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", s.lower().replace("ё", "е")).strip()


# Короткие названия, которыми ученики называют олимпиады.
ALIASES = {
    "жаутык": "izho",
    "izho": "izho",
    "всесиб": "всесибирская",
    "курчатов": "курчатов",
    "всош": "всероссийская",
    "всеросс": "всероссийская",
    "высшая проба": "высшая проба",
    "вышка": "высшая проба",
    "ммо": "московская математическая",
    "московская": "московская математическая",
    "турнир городов": "турнир городов",
    "тг": "турнир городов",
    "белфо": "беларусь",
    "belpho": "беларусь",
    "ipho": "ipho",
    "ифо": "ipho",
    "usapho": "usapho",
    "apmo": "apmo",
}


def matches(p: Problem, query: str) -> bool:
    """Подходит ли задача под запрос вида «жаутыковская физика» (по названию олимпиады и теме)."""
    q = _norm(query)
    if not q:
        return True
    subject = "математика math" if p.subject == "math" else "физика physics"
    hay = _norm(f"{p.source.olympiad} {p.source.track_title()} {p.topic} {p.title} {subject}")
    words = []
    for alias, target in ALIASES.items():
        if alias in q:
            words.append(_norm(target))
            q = q.replace(alias, " ")
    words += [
        w for w in q.split() if len(w) >= 3 and w not in {"задачи", "задача", "типа", "как", "олимпиады"}
    ]
    # Грубая поддержка русских окончаний: сравниваем по началу слова.
    return all(w[: max(4, len(w) - 2)] in hay for w in words) if words else True


@dataclass
class Contest:
    id: str
    title: str
    olympiad: str
    stage: str
    year: int | None
    grade: int | None
    subject: str
    problems: list[Problem]
    tour: int | None = None


TOUR_RE = re.compile(r"(?i)(?:day|den|день|tur|тур)[ _.-]*(\d)|(\d)[ _.-]*(?:day|den|день)")


def tour_of(p: Problem) -> int | None:
    """Номер тура/дня из имени файла (day_1, 2day, tur2, 3etap2026day1…). Олимпиада даёт время на один тур."""
    if p.source.stage == "distance":
        return None  # дистанционные туры идут несколько дней — не тур «на время»
    m = TOUR_RE.search((p.source.url or "").rsplit("/", 1)[-1].split("#")[0])
    return int(m.group(1) or m.group(2)) if m else None


def contest_id(p: Problem) -> str:
    tour = tour_of(p)
    return f"{p.source.track_id}-{p.source.year or 0}-{p.subject[:4]}-{p.source.grade or 0}" + (
        f"-t{tour}" if tour else ""
    )


_cache: dict[int, dict[str, Contest]] = {}


def build_contests(bank: dict[str, Problem]) -> dict[str, Contest]:
    """Наборы считаются один раз на загруженный банк (банк закэширован в load_bank)."""
    if id(bank) not in _cache:
        _cache.clear()
        _cache[id(bank)] = _build(bank)
    return _cache[id(bank)]


def _build(bank: dict[str, Problem]) -> dict[str, Contest]:
    groups: dict[str, list[Problem]] = {}
    for p in bank.values():
        if p.source.stage == "other" and p.source.olympiad.startswith("Демо"):
            continue
        groups.setdefault(contest_id(p), []).append(p)
    out = {}
    for cid, ps in groups.items():
        if len(ps) < MIN_CONTEST_PROBLEMS:
            continue
        ps.sort(key=lambda p: (p.source.number or 0, p.id))
        s = ps[0].source
        tour = tour_of(ps[0])
        parts = [
            s.track_title(),
            str(s.year) if s.year else None,
            f"{s.grade} класс" if s.grade else None,
            f"тур {tour}" if tour else None,
        ]
        subject = "математика" if ps[0].subject == "math" else "физика"
        out[cid] = Contest(
            id=cid,
            title=", ".join(x for x in parts if x) + f" ({subject})",
            olympiad=s.olympiad,
            stage=s.stage,
            year=s.year,
            grade=s.grade,
            subject=ps[0].subject,
            problems=ps,
            tour=tour,
        )
    return out


def search_problems(
    bank: dict[str, Problem],
    points: Callable[[Problem], int],
    solved: set[str],
    *,
    query: str = "",
    subject: str | None = None,
    min_points: int | None = None,
    max_points: int | None = None,
    grade: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Нерешённые задачи под запрос, от лёгких к трудным (по баллам)."""
    found = []
    for p in bank.values():
        if p.id in solved or p.source.olympiad.startswith("Демо"):
            continue
        if subject and p.subject != subject:
            continue
        if grade and p.source.grade and abs(p.source.grade - grade) > 1:
            continue
        pts = points(p)
        if (min_points and pts < min_points) or (max_points and pts > max_points):
            continue
        if not matches(p, query):
            continue
        found.append((pts, p))
    found.sort(key=lambda x: (x[0], x[1].id))
    return [
        {"id": p.id, "title": p.title, "source": p.source.label(), "topic": p.topic, "points": pts}
        for pts, p in found[: max(1, min(limit, 8))]
    ]
