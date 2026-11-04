"""Баллы за задачи — без ярлыков «лёгкая/сложная», только число.

1. Стартовые баллы задаются по этапу олимпиады, классу и номеру задачи
   (или вручную полем points).
2. Дальше баллы подстраиваются по статистике: если задачу решают почти все,
   её цена снижается, если почти никто — растёт.
3. Награда ученику уменьшается за открытые подсказки; после просмотра
   разбора за оригинал баллы не дают, а за решённый вариант — половину.
"""

from __future__ import annotations

from .bank import Problem

STAGE_BASE = {
    "school": 100,
    "qualifying": 150,
    "distance": 150,
    "city": 200,
    "region": 300,
    "republic": 450,
    "final": 550,
    "international": 600,
    "other": 200,
}

HINT_FACTORS = [1.0, 0.8, 0.6, 0.4]  # индекс = сколько подсказок открыто
VARIANT_AFTER_SOLUTION_FACTOR = 0.5
SMOOTHING = 10  # «виртуальных» попыток в априорной оценке


def _round_to(x: float, step: int) -> int:
    return int(step * round(x / step))


def base_points(problem: Problem) -> int:
    if problem.points is not None:
        return problem.points
    src = problem.source
    pts = STAGE_BASE[src.stage]
    if src.grade:
        pts += max(0, src.grade - 7) * 25
    if src.number:
        pts += (src.number - 1) * 75
    return max(50, _round_to(pts, 50))


def expected_solve_rate(base: int) -> float:
    """Априорная доля решивших для задачи с такими баллами."""
    return min(0.9, max(0.1, 1 - base / 1000))


def dynamic_points(base: int, attempted: int, solved: int) -> int:
    """Подстройка по статистике (байесовское сглаживание)."""
    p0 = expected_solve_rate(base)
    rate = (solved + SMOOTHING * p0) / (attempted + SMOOTHING)
    factor = (p0 / rate) ** 0.5
    factor = min(2.0, max(0.5, factor))
    return max(10, _round_to(base * factor, 10))


def reward(points: int, hints_used: int, solution_viewed: bool, via_variant: bool) -> int:
    hints_used = max(0, min(hints_used, len(HINT_FACTORS) - 1))
    factor = HINT_FACTORS[hints_used]
    if solution_viewed:
        if not via_variant:
            return 0
        factor *= VARIANT_AFTER_SOLUTION_FACTOR
    return _round_to(points * factor, 5)
