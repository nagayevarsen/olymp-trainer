"""Ответы-формулы: «a = 17/29·g», «T = 2π√(l/g)».

Проверка без символьной алгебры: подставляем в формулу ученика и в официальную одни и те же
случайные положительные значения всех обозначений и сравниваем числа. Совпали на нескольких
наборах — формулы равносильны (так засчитываются √(2gh), (2*g*h)^0.5 и т. п.).

Как и в mathparse, строка ученика сначала проходит белый список символов и имён,
а гигантские степени отсекаются, поэтому выполнить произвольный код или повесить сервер нельзя.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

MAX_LEN = 160
SAMPLES = 6
REL_TOL = 1e-3  # округлённые коэффициенты (0.5862 g вместо 17/29 g) засчитываются

_FUNCS = {
    "sqrt": sympy.sqrt,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "tg": sympy.tan,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "arcsin": sympy.asin,
    "arccos": sympy.acos,
    "arctg": sympy.atan,
    "exp": sympy.exp,
    "ln": sympy.log,
    "log": sympy.log,
}
_CONSTS = {"pi": sympy.pi}
_GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta", "η": "eta",
    "θ": "theta", "κ": "kappa", "λ": "lam", "μ": "mu", "ν": "nu", "ξ": "xi", "ρ": "rho",
    "σ": "sigma", "τ": "tau", "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
    "Δ": "Delta", "Φ": "Phi", "Ω": "Omega",
}  # fmt: skip
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


class FormulaError(ValueError):
    pass


def normalize(s: str) -> str:
    s = s.strip().translate(_SUB)
    s = re.sub(r"^\s*[A-Za-zА-Яа-яα-ωΑ-Ω][\w']*\s*=\s*", "", s)  # «a = …» → «…»
    for a, b in [
        ("−", "-"),
        ("–", "-"),
        ("×", "*"),
        ("·", "*"),
        ("⋅", "*"),
        (":", "/"),
        ("²", "^2"),
        ("³", "^3"),
        ("π", " pi "),
    ]:
        s = s.replace(a, b)
    for g, name in _GREEK.items():
        s = s.replace(g, f" {name} ")
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = re.sub(r"√\s*(\([^()]*\)|[A-Za-z0-9_.]+)", r" sqrt(\1)", s)
    s = re.sub(r"([A-Za-z]+)_\{?([A-Za-z0-9]+)\}?", r"\1\2", s)  # v_0, v_{0} → v0
    return s


def _split(word: str, names: list[str]) -> str | None:
    """Разбить слово на известные обозначения («mgh» → «m g h»), предпочитая длинные имена."""
    best: dict[int, list[str]] = {0: []}
    for i in range(len(word)):
        if i not in best:
            continue
        for n in sorted(names, key=len, reverse=True):
            if word.startswith(n, i) and i + len(n) not in best:
                best[i + len(n)] = best[i] + [n]
    parts = best.get(len(word))
    return " ".join(parts) if parts else None


def parse(expr: str, variables: list[str] | tuple[str, ...]) -> sympy.Expr:
    """Разобрать формулу, в которой можно использовать только эти обозначения. Иначе FormulaError."""
    s = normalize(expr)
    if not s:
        raise FormulaError("Пустой ответ")
    if len(s) > MAX_LEN:
        raise FormulaError("Слишком длинная формула")
    names = {v: sympy.Symbol(v, positive=True) for v in variables}
    allowed = {**_FUNCS, **_CONSTS, **names}
    # «mg», «2gh» — слитно записанное произведение известных обозначений → «m g», «g h».
    s = re.sub(
        r"[A-Za-z_][A-Za-z0-9_]*",
        lambda m: (
            m.group(0) if m.group(0) in allowed else (_split(m.group(0), [*names, *_CONSTS]) or m.group(0))
        ),
        s,
    )
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s):
        if word not in allowed:
            listed = ", ".join(variables) if variables else "нет"
            raise FormulaError(f"Неизвестное обозначение «{word}». Можно использовать: {listed}")
    if re.search(r"[^A-Za-z0-9_+\-*/^(). ]", s):
        raise FormulaError("Недопустимые символы в формуле")
    if len(re.findall(r"\^|\*\*", s)) > 4 or re.search(r"(\^|\*\*)\s*\(?\s*\d{3,}", s):
        raise FormulaError("Слишком большая степень")
    try:
        return parse_expr(s, local_dict=allowed, transformations=_TRANSFORMS, evaluate=False)
    except Exception as exc:  # sympy бросает много разных исключений
        raise FormulaError("Не удалось разобрать формулу") from exc


def _value(e: sympy.Expr, point: dict) -> float:
    v = complex(e.evalf(15, subs=point))
    if abs(v.imag) > 1e-9 * max(1.0, abs(v.real)) or not math.isfinite(v.real):
        raise FormulaError("Формула не даёт действительного числа")
    return v.real


def equivalent(a: sympy.Expr, b: sympy.Expr, variables: list[str] | tuple[str, ...], seed: int = 7) -> bool:
    """Совпадают ли формулы на нескольких случайных наборах положительных значений."""
    rng = random.Random(seed)
    syms = [sympy.Symbol(v, positive=True) for v in variables]
    good = 0
    for _ in range(SAMPLES * 3):
        point = {s: rng.uniform(0.6, 2.4) for s in syms}
        try:
            x, y = _value(a, point), _value(b, point)
        except (FormulaError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            continue  # точка вне области определения (например, корень из отрицательного) — берём другую
        if not math.isclose(x, y, rel_tol=REL_TOL, abs_tol=1e-12):
            return False
        good += 1
        if good >= SAMPLES:
            return True
    return False


@dataclass
class FormulaResult:
    status: str  # correct / wrong / unparsable
    message: str

    @property
    def correct(self) -> bool:
        return self.status == "correct"


def check(expected: str, variables: dict[str, str] | list[str], raw: str) -> FormulaResult:
    names = list(variables)
    try:
        student = parse(raw, names)
    except FormulaError as exc:
        return FormulaResult("unparsable", f"{exc}. Пример записи: 17*g/29 или 2*pi*sqrt(l/g).")
    official = parse(expected, names)
    if equivalent(student, official, names):
        return FormulaResult("correct", "Верно!")
    return FormulaResult("wrong", "Формула не совпадает с ответом. Проверь вывод или открой подсказку.")
