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
        "Всероссийская",
        "region",
        "math",
        235,
        "Решения регионального этапа ВсОШ по математике: «составляет 3 часа 55 минут»",
        "https://vos.olimpiada.ru/upload/files/Arhive_tasks/2022-23/reg/math/sol-math-9-tur2-reg-22-23.pdf",
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
]


def rule_for(olympiad: str, stage: str, subject: str) -> Rule | None:
    for r in RULES:
        if r.olympiad in olympiad and (r.stage in (None, stage)) and (r.subject in (None, subject)):
            return r
    return None


def available_list() -> list[str]:
    """Человекочитаемый список олимпиад, для которых известно официальное время."""
    names = {
        "Жаутыковская": "Жаутыковская (IZhO)",
        "APMO": "APMO",
        "Эйлера": "Эйлера (региональный этап)",
        "Всероссийская": "ВсОШ по математике (региональный этап)",
        "Всесибирская": "Всесибирская по математике",
    }
    return list(dict.fromkeys(names[r.olympiad] for r in RULES))
