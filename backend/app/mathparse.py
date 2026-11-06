"""Безопасный разбор числового ответа ученика: "1,5", "2√3", "3/4", "2*pi", "1.2e3".

Используется sympy, но строка сначала проходит через белый список символов
и имён, поэтому произвольный код выполнить нельзя.
"""

from __future__ import annotations

import math
import re

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

MAX_LEN = 80

_ALLOWED_NAMES = {
    "sqrt": sympy.sqrt,
    "pi": sympy.pi,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "tg": sympy.tan,
    "ln": sympy.log,
    "log": sympy.log,
    "exp": sympy.exp,
}

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

_REPLACEMENTS = [
    ("−", "-"),
    ("–", "-"),
    ("×", "*"),
    ("·", "*"),
    ("⋅", "*"),
    (":", "/"),
    ("π", "pi"),
    ("²", "^2"),
    ("³", "^3"),
]


class ParseError(ValueError):
    pass


def normalize(s: str) -> str:
    s = s.strip()
    for a, b in _REPLACEMENTS:
        s = s.replace(a, b)
    # десятичная запятая: 1,5 -> 1.5
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # √3, √(x+1), 2√3
    s = re.sub(r"√\s*(\d+(?:\.\d+)?|\([^()]*\)|[a-z]+)", r"sqrt(\1)", s)
    return s


def parse_number(s: str) -> float:
    """Вычислить числовое выражение. Бросает ParseError, если это не число."""
    if not s or not s.strip():
        raise ParseError("Пустой ответ")
    expr = normalize(s)
    if len(expr) > MAX_LEN:
        raise ParseError("Слишком длинное выражение")
    # белый список: цифры, операции, скобки, точка, пробелы и разрешённые имена
    rest = expr
    for name in sorted(_ALLOWED_NAMES, key=len, reverse=True):
        rest = rest.replace(name, " ")
    if re.search(r"[^0-9eE+\-*/^(). ]", rest):
        raise ParseError("Недопустимые символы в ответе")
    if re.search(r"[eE]", rest) and not re.search(r"\d\.?\d*[eE][+-]?\d", expr):
        raise ParseError("Недопустимые символы в ответе")
    # защита от гигантских степеней вроде 9^9^9
    if len(re.findall(r"\^|\*\*", expr)) > 2 or re.search(r"(\^|\*\*)\s*\(?\s*\d{4,}", expr):
        raise ParseError("Слишком большая степень")
    try:
        # evaluate=False: sympy не считает выражение точно (999^999^999 повесил бы сервер),
        # дерево вычисляется ниже обычными float с проверкой переполнения.
        tree = parse_expr(expr, local_dict=dict(_ALLOWED_NAMES), transformations=_TRANSFORMS, evaluate=False)
        value = _eval(tree)
    except ParseError:
        raise
    except Exception as exc:  # sympy и math бросают много разных исключений
        raise ParseError("Не удалось разобрать число") from exc
    if not math.isfinite(value):
        raise ParseError("Ответ должен быть действительным числом")
    return value


_FUNCS = {
    sympy.sin: math.sin,
    sympy.cos: math.cos,
    sympy.tan: math.tan,
    sympy.exp: math.exp,
}


def _eval(node) -> float:
    """Посчитать дерево sympy в float. Только числа, + − × ÷, степени и функции из белого списка."""
    if node is sympy.pi:
        return math.pi
    if node is sympy.E:
        return math.e
    if node.is_Number:
        return float(node)
    if isinstance(node, sympy.Add):
        return math.fsum(_eval(a) for a in node.args)
    if isinstance(node, sympy.Mul):
        out = 1.0
        for a in node.args:
            out *= _eval(a)
        return out
    if isinstance(node, sympy.Pow):
        base, exp = _eval(node.args[0]), _eval(node.args[1])
        if base < 0 and not float(exp).is_integer():
            raise ParseError("Ответ должен быть действительным числом")
        if base == 0 and exp < 0:
            raise ParseError("Деление на ноль")
        return math.pow(base, exp)  # OverflowError при гигантских степенях
    if isinstance(node, sympy.log):
        return math.log(*[_eval(a) for a in node.args])
    if node.func in _FUNCS and len(node.args) == 1:
        return _FUNCS[node.func](_eval(node.args[0]))
    raise ParseError("Не удалось разобрать число")
