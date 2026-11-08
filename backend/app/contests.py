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

MIN_CONTEST_PROBLEMS = 4


def _norm(s: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", s.lower().replace("ё", "е")).strip()


# Все названия, под которыми олимпиаду ищут: полное официальное, фамилия, «олимпиада имени …»,
# аббревиатуры и прозвища. Ключ — кусок нормализованного названия олимпиады из банка.
OLYMPIAD_NAMES = {
    "izho": "жаутыков жаутыковская олимпиада имени жаутыкова ижо izho международная жаутыковская",
    "городская жаутыковская": "жаутыков жаутыковская олимпиада имени жаутыкова алматы городская",
    "эйлера": "эйлер эйлера леонард леонарда олимпиада имени эйлера",
    "смагулова": "смагулов смагулова смагуловская шалтай олимпиада имени смагулова",
    "республиканская олимпиада": "республиканская республика казахстан рмо",
    "юниорская": "юниор юниорская юниоры казахстан",
    "кбо": "кбо казахстан білім олимпиадасы знаний",
    "высшая проба": "вшэ вышка высшая проба высшая школа экономики",
    "ipho": "ipho ифо международная физическая олимпиада физики",
    "apmo": "apmo азиатско тихоокеанская математическая олимпиада",
    "турнир городов": "тг турнир городов",
    "курчатов": "курчатов курчатовская олимпиада",
    "всесибирская": "всесиб всесибирская сибирская сибирь олимпиада сибири",
    "московская математическая": "ммо москва московская математическая олимпиада",
}
STOP_WORDS = {"задачи", "задача", "типа", "как", "олимпиада", "олимпиады", "олимпиаду", "имени", "им"}


def _same_word(w: str, h: str) -> bool:
    """Слова одного корня: «смагуловская» ~ «смагулова», «жаут» ~ «жаутыковская». Короткие — только целиком."""
    if min(len(w), len(h)) < 4:
        return w == h
    common = 0
    for a, b in zip(w, h, strict=False):
        if a != b:
            break
        common += 1
    return common >= max(4, min(len(w), len(h)) - 3)


def _names(olympiad: str) -> str:
    n = _norm(olympiad)
    return " ".join(extra for key, extra in OLYMPIAD_NAMES.items() if key in n)


def matches(p: Problem, query: str, partial: bool = False) -> bool:
    """Подходит ли задача под запрос вида «жаутыковская физика» (по названиям олимпиады и теме).

    partial=True: достаточно совпадения хотя бы одного слова запроса («возможно подходящая»).
    """
    words = [w for w in _norm(query).split() if len(w) >= 2 and w not in STOP_WORDS]
    if not words:
        return True
    subject = "математика math" if p.subject == "math" else "физика physics"
    hay = _norm(
        f"{p.source.olympiad} {_names(p.source.olympiad)} {p.source.track_title()} {p.topic} {p.title} {subject}"
    ).split()
    found = [any(_same_word(w, h) for h in hay) for w in words]
    return any(found) if partial else all(found)


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


_cache: dict = {}  # {"bank": банк, "contests": наборы}


def build_contests(bank: dict[str, Problem]) -> dict[str, Contest]:
    """Наборы считаются один раз на загруженный банк (банк закэширован в load_bank)."""
    # Храним сам банк, а не только id: после перезагрузки банка id нового словаря может совпасть.
    if _cache.get("bank") is not bank:
        _cache.clear()
        _cache.update(bank=bank, contests=_build(bank))
    return _cache["contests"]


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
