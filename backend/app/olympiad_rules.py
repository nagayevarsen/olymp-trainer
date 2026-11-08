"""Официальные условия олимпиад для пробной олимпиады на время: длительность тура и баллы за задачу.

Только подтверждённые данные — у каждой записи есть источник. Если для олимпиады записи нет,
пробная олимпиада на время для неё недоступна (время не угадываем).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    olympiad: str  # подстрока названия олимпиады в банке
    stage: str | None  # этап (None — любой)
    subject: str | None  # math / physics (None — любой)
    minutes: int  # длительность одного тура
    source_name: str
    source_url: str
    points_per_problem: int | None = None  # официальные баллы за задачу, если они одинаковые
    grades: tuple[int, int] | None = None  # для каких классов (включительно); None — для всех
    tours: tuple[int, ...] | None = None  # для каких туров; None — для всех (и когда тур неизвестен)


@dataclass(frozen=True)
class OfficialSet:
    """Состав официального варианта: сколько в нём задач и равноценны ли они."""

    olympiad: str  # подстрока названия олимпиады в банке
    stage: str
    problems: int | None  # None — число задач не подтверждено документом
    tour: int | None = None  # None — для любого тура
    equal_weight: bool = False  # все задачи стоят одинаково
    source: str = ""


OFFICIAL_SETS: list[OfficialSet] = [
    OfficialSet(
        "Смагулова",
        "city",
        20,
        tour=1,
        equal_weight=True,
        source="matol.kz/olympiads/1227: «1 тур», задачи №1–№20",
    ),
    OfficialSet(
        "Смагулова",
        "city",
        5,
        tour=2,
        equal_weight=True,
        source="matol.kz/olympiads/1235: «2 тур», задачи №1–№5",
    ),
    OfficialSet(
        "Смагулова", "city", None, equal_weight=True, source="городские этапы: все задачи равноценны"
    ),
    OfficialSet(
        "Городская Жаутыковская",
        "city",
        20,
        equal_weight=True,
        source="по данным команды: 20 задач, все равноценны",
    ),
    OfficialSet(
        "APMO",
        "international",
        5,
        equal_weight=True,
        source="apmo-official.org/regulations: five questions, 7 points each",
    ),
]


def official_set(olympiad: str, stage: str, tour: int | None = None) -> OfficialSet | None:
    """Первый подходящий состав: запись для конкретного тура идёт раньше общей записи об олимпиаде."""
    for s in OFFICIAL_SETS:
        if s.olympiad in olympiad and s.stage == stage and s.tour in (None, tour):
            return s
    return None


RULES: list[Rule] = [
    Rule(
        "Жаутыковская",
        "international",
        "math",
        270,
        "Положение о Международной Жаутыковской олимпиаде, п. 12",
        "https://daryn.kz/pol514/ZhautyqOru.pdf",
    ),
    Rule(
        "Жаутыковская",
        "international",
        "physics",
        270,
        "Положение о Международной Жаутыковской олимпиаде, п. 12 (теоретический тур)",
        "https://daryn.kz/pol514/ZhautyqOru.pdf",
    ),
    Rule(
        "APMO",
        "international",
        "math",
        240,
        "APMO Regulations: one four-hour paper, five questions, 7 points each",
        "https://www.apmo-official.org/regulations",
        points_per_problem=7,
    ),
    Rule(
        "Эйлера",
        "region",
        "math",
        235,
        "Региональный этап: два тура по 3 ч 55 мин",
        "https://postupi.online/olimpiada/olimpiada-ejlera/etap/regionalnyj-etap/",
    ),
    Rule(
        "Эйлера",
        "final",
        "math",
        270,
        "Заключительный этап: «Продолжительность каждого тура – 4,5 часа»",
        "https://matol.kz/news/170",
    ),
    Rule(
        "Всесибирская",
        "final",
        "math",
        240,
        "Решения заключительного этапа: «Время выполнения задания 4 астрономических часа»",
        "https://sesc.nsu.ru/upload/iblock/fad/2019_3_math_s.pdf",
    ),
    Rule(
        "Всесибирская",
        "qualifying",
        "math",
        240,
        "Решения отборочного этапа: «Время выполнения 4 астрономических часа»",
        "https://sesc.nsu.ru/olymp-vsesib/sections/maths/",
    ),
    Rule(
        "Смагулова",
        "city",
        "math",
        180,
        "Объявление ЦОП «Аль-Фараби»: II городской этап — «5 заданий письменной олимпиады на 3 часа»",
        "https://matol.kz/announce/263",
        tours=(2,),  # время в объявлении — у письменного тура из 5 задач; у 1 тура (20 задач) времени нет
    ),
]


def rule_for(
    olympiad: str, stage: str, subject: str, grade: int | None = None, tour: int | None = None
) -> Rule | None:
    for r in RULES:
        if r.olympiad in olympiad and (r.stage in (None, stage)) and (r.subject in (None, subject)):
            if r.grades and not (grade and r.grades[0] <= grade <= r.grades[1]):
                continue
            if r.tours and tour is not None and tour not in r.tours:
                continue
            return r
    return None


def available_list(have: set[str] | None = None) -> list[str]:
    """Человекочитаемый список олимпиад, для которых известно официальное время."""
    names = {
        "Жаутыковская": "Жаутыковская (IZhO)",
        "APMO": "APMO",
        "Эйлера": "Эйлера (региональный и заключительный этапы)",
        "Всесибирская": "Всесибирская по математике",
        "Смагулова": "Смагуловская (городской этап)",
    }
    # have — названия олимпиад, у которых в банке есть полный вариант; None — не фильтровать.
    return list(
        dict.fromkeys(
            names[r.olympiad] for r in RULES if have is None or any(r.olympiad in name for name in have)
        )
    )
