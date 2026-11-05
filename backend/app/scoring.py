"""Баллы за задачи — простая шкала от 3 до 10, без ярлыков «лёгкая/сложная».

1. Стартовые баллы задаются по этапу олимпиады, классу и номеру задачи
   (или вручную полем points). Самая сложная задача — 10, самая простая — 3.
2. Дальше баллы подстраиваются по статистике (не больше чем на ±2):
   если задачу решают почти все, она дешевле, если почти никто — дороже.
3. Награда ученику уменьшается за открытые подсказки; после просмотра
   разбора за оригинал баллы не дают, а за решённый вариант — половину.
"""

from __future__ import annotations

from .bank import Problem

MIN_POINTS = 3
MAX_POINTS = 10

STAGE_BASE = {
    "school": 3,
    "qualifying": 4,
    "distance": 4,
    "district": 4,
    "city": 5,
    "region": 6,
    "republic": 7,
    "final": 7,
    "international": 8,
    "other": 5,
}

HINT_FACTORS = [1.0, 0.8, 0.6, 0.4]  # индекс = сколько подсказок открыто
VARIANT_AFTER_SOLUTION_FACTOR = 0.5
SMOOTHING = 10  # «виртуальных» попыток в априорной оценке


def clamp(x: float) -> int:
    return int(min(MAX_POINTS, max(MIN_POINTS, round(x))))


def base_points(problem: Problem) -> int:
    if problem.points is not None:
        return clamp(problem.points)
    src = problem.source
    pts = STAGE_BASE[src.stage]
    if src.grade and src.grade >= 10:
        pts += 1
    if src.number:
        pts += min(2, (src.number - 1) // 2)  # дальние задачи варианта обычно труднее
    return clamp(pts)


def expected_solve_rate(base: int) -> float:
    """Априорная доля решивших для задачи с такими баллами."""
    return min(0.9, max(0.1, 1 - (base - 2) / 9))


def dynamic_points(base: int, attempted: int, solved: int) -> int:
    """Подстройка по статистике (байесовское сглаживание), не больше чем на ±2 балла."""
    p0 = expected_solve_rate(base)
    rate = (solved + SMOOTHING * p0) / (attempted + SMOOTHING)
    shift = max(-2.0, min(2.0, 2.5 * (p0 - rate) / max(p0, 0.1)))
    return clamp(base + shift)


def reward(points: int, hints_used: int, solution_viewed: bool, via_variant: bool) -> int:
    hints_used = max(0, min(hints_used, len(HINT_FACTORS) - 1))
    factor = HINT_FACTORS[hints_used]
    if solution_viewed:
        if not via_variant:
            return 0
        factor *= VARIANT_AFTER_SOLUTION_FACTOR
    return max(1, round(points * factor))


def scale_for_contest(base: list[int]) -> list[int]:
    """Баллы внутри варианта олимпиады: самая сложная задача — 10, самая простая — 3,
    остальные — пропорционально (если официальных баллов за задачи нет)."""
    if not base:
        return []
    lo, hi = min(base), max(base)
    if hi == lo:
        return [MAX_POINTS if len(base) == 1 else 7] * len(base)
    return [clamp(MIN_POINTS + (b - lo) * (MAX_POINTS - MIN_POINTS) / (hi - lo)) for b in base]
