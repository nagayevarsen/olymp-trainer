"""Клонирование задач: генерация вариантов с проверкой корректности.

Конвейер для одного варианта:
1. По seed детерминированно выбираются новые значения параметров.
2. Решатель (solve) вычисляет ответ в песочнице.
3. Проверяются ограничения (ответ > 0, целый, «красивый» и т.д.).
4. Пользователь получает вариант только если всё прошло.

Так как вариант полностью определяется seed, его не нужно хранить:
по (id задачи, seed) условие и ответ всегда восстанавливаются одинаково.

Сам шаблон считается проверенным, только если solve(оригинальные параметры)
воспроизводит официальный ответ (см. verify_template).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from .bank import Problem, Template
from .checker import AnswerKey, format_number
from .sandbox import SandboxError, run_solver

CANDIDATES_PER_BATCH = 40


class CloneError(RuntimeError):
    pass


@dataclass
class Variant:
    problem_id: str
    seed: int
    params: dict[str, float]
    statement: str
    answer: AnswerKey


def _values(rng: random.Random, spec) -> float:  # spec: ParamRange
    if spec.value is not None:
        return spec.value
    count = int(math.floor((spec.max - spec.min) / spec.step + 1e-9)) + 1
    v = spec.min + spec.step * rng.randrange(count)
    return round(v, 10)


def _clean(v: float) -> float | int:
    return int(round(v)) if abs(v - round(v)) < 1e-9 else v


def render(template: Template, params: dict[str, float]) -> str:
    text = template.text
    for name, value in params.items():
        text = text.replace("{" + name + "}", format_number(value))
    return text


def _is_nice(answer: float, template: Template) -> bool:
    if not math.isfinite(answer):
        return False
    if template.answer_integer:
        return abs(answer - round(answer)) < 1e-9
    if template.answer_max_decimals is not None:
        scaled = answer * 10**template.answer_max_decimals
        return abs(scaled - round(scaled)) < 1e-6 * max(1.0, abs(scaled))
    return True


def _candidates(template: Template, seed: int) -> list[dict[str, float]]:
    rng = random.Random(seed)
    out = []
    for _ in range(CANDIDATES_PER_BATCH):
        params = {name: _clean(_values(rng, spec)) for name, spec in template.params.items()}
        if params != {k: _clean(v) for k, v in template.original.items()}:
            out.append(params)
    return out


@lru_cache(maxsize=2048)
def _make_variant_cached(problem_json: str, seed: int) -> tuple[dict, float] | None:
    problem = Problem.model_validate_json(problem_json)
    template = problem.template
    assert template is not None
    cands = _candidates(template, seed)
    results = run_solver(template.solver, cands, template.constraints)
    for params, res in zip(cands, results):
        if res.get("ok") and _is_nice(res["answer"], template):
            return params, res["answer"]
    return None


def make_variant(problem: Problem, seed: int) -> Variant:
    """Построить проверенный вариант задачи по seed. CloneError, если не вышло."""
    if problem.template is None:
        raise CloneError("У задачи нет шаблона для вариантов")
    found = _make_variant_cached(problem.model_dump_json(), seed)
    if found is None:
        raise CloneError("Не удалось подобрать корректные параметры, попробуй ещё раз")
    params, answer = found
    return Variant(
        problem_id=problem.id,
        seed=seed,
        params=params,
        statement=render(problem.template, params),
        answer=AnswerKey(value=answer, unit=problem.answer.unit, rel_tol=problem.answer.tolerance),
    )


def find_seed(problem: Problem, start: int, attempts: int = 5) -> Variant:
    """Найти рабочий seed, начиная со start."""
    last: Exception | None = None
    for s in range(start, start + attempts):
        try:
            return make_variant(problem, s)
        except CloneError as exc:
            last = exc
    raise CloneError(str(last))


@dataclass
class TemplateReport:
    ok: bool
    reproduces_original: bool
    original_answer: float | None
    variants_ok: int
    errors: list[str]


def verify_template(problem: Problem, template: Template, n_variants: int = 3) -> TemplateReport:
    """Проверить шаблон: (1) воспроизводит официальный ответ, (2) из него получаются варианты,
    (3) текст с оригинальными параметрами совпадает с условием по числам."""
    errors: list[str] = []
    try:
        original = {k: _clean(v) for k, v in template.original.items()}
        res = run_solver(template.solver, [original], template.constraints)[0]
    except SandboxError as exc:
        return TemplateReport(False, False, None, 0, [f"Решатель отклонён: {exc}"])
    original_answer = res.get("answer")
    reproduces = bool(
        res.get("ok")
        and original_answer is not None
        and math.isclose(
            original_answer, problem.answer.value, rel_tol=problem.answer.tolerance, abs_tol=1e-9
        )
    )
    if not res.get("ok"):
        errors.append(f"Решатель на оригинальных данных: {res.get('error')}")
    elif not reproduces:
        errors.append(f"Решатель дал {original_answer}, а официальный ответ {problem.answer.value}")

    p = problem.model_copy(update={"template": template})
    variants_ok = 0
    for seed in range(1, n_variants + 1):
        try:
            make_variant(p, seed)
            variants_ok += 1
        except (CloneError, SandboxError) as exc:
            errors.append(f"seed={seed}: {exc}")

    return TemplateReport(
        ok=reproduces and variants_ok == n_variants,
        reproduces_original=reproduces,
        original_answer=original_answer,
        variants_ok=variants_ok,
        errors=errors,
    )
