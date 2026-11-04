"""Проверка ответа ученика: число + (для физики) единицы измерения с анализом размерности."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from .mathparse import ParseError, parse_number
from .units import Quantity, UnitError, describe_dim, parse_unit

Status = Literal["correct", "wrong", "wrong_dimension", "unparsable", "unit_missing"]


@dataclass
class AnswerKey:
    value: float
    unit: str | None = None  # единица, в которой записан value ("с", "км/ч"); None — безразмерный
    rel_tol: float = 0.01  # физические ответы часто округляют — 1%; для математики передаётся ~0
    abs_tol: float = 1e-9


@dataclass
class CheckResult:
    status: Status
    message: str

    @property
    def correct(self) -> bool:
        return self.status in ("correct", "unit_missing")


def split_answer(raw: str) -> tuple[str, str]:
    """Разделить "4,5 м/с" на ("4,5", "м/с"). Если всё — число, единиц нет."""
    raw = raw.strip()
    try:
        parse_number(raw)
        return raw, ""
    except ParseError:
        pass
    # ищем самую левую позицию, где справа — корректные единицы, а слева — число
    for m in re.finditer(r"[A-Za-zА-Яа-яЁёΩµμ°%]", raw):
        left, right = raw[: m.start()].strip(), raw[m.start() :].strip()
        if not left:
            continue
        try:
            parse_unit(right)
            parse_number(left)
            return left, right
        except (UnitError, ParseError):
            continue
    raise ParseError("Не удалось разобрать ответ")


def _close(a: float, b: float, key: AnswerKey) -> bool:
    return math.isclose(a, b, rel_tol=key.rel_tol, abs_tol=key.abs_tol)


def check_answer(key: AnswerKey, raw: str) -> CheckResult:
    try:
        num_str, unit_str = split_answer(raw)
        value = parse_number(num_str)
    except ParseError:
        return CheckResult(
            "unparsable",
            "Не получилось прочитать ответ. Пример: 4,5 или 2√3 или 12 м/с.",
        )

    expected_q: Quantity = parse_unit(key.unit)
    expected_si = key.value * expected_q.factor

    if not unit_str:
        if expected_q.dim != (0, 0, 0, 0, 0, 0):
            # число без единиц: считаем, что ученик имел в виду единицы из условия
            if _close(value, key.value, key):
                return CheckResult(
                    "unit_missing",
                    f"Верно! Но в олимпиаде без единиц могут снять баллы: пиши «{_fmt(value)} {key.unit}».",
                )
            return CheckResult("wrong", "Неверно. Подсказка: указывай единицы — это помогает ловить ошибки.")
        if _close(value, key.value, key):
            return CheckResult("correct", "Верно!")
        return CheckResult("wrong", "Неверно. Попробуй ещё раз или открой подсказку.")

    try:
        user_q = parse_unit(unit_str)
    except UnitError as exc:
        return CheckResult("unparsable", str(exc))

    if user_q.dim != expected_q.dim:
        got = describe_dim(user_q.dim)
        want = describe_dim(expected_q.dim)
        return CheckResult(
            "wrong_dimension",
            f"Размерность не сходится: у тебя получилась {got}, а спрашивают {want}. "
            "Проверь формулу — где-то потерялась или лишняя величина.",
        )

    if _close(value * user_q.factor, expected_si, key):
        return CheckResult("correct", "Верно!")
    return CheckResult("wrong", "Размерность правильная, но число не сходится. Проверь вычисления.")


def _fmt(x: float) -> str:
    return format_number(x)


def format_number(x: float, max_decimals: int = 4) -> str:
    """12.0 -> "12", 0.125 -> "0,125" (русская запятая)."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    s = f"{x:.{max_decimals}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")
