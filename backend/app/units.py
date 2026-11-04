"""Единицы измерения и размерности (анализ размерностей для физики).

Размерность хранится как кортеж степеней базовых величин СИ:
(длина, масса, время, сила тока, температура, количество вещества).

Поддерживаются русские и латинские обозначения, приставки (к, М, м, мк, н, ...),
степени (м^2, м², с^-1), умножение (·, *, пробел), деление и скобки:
"м/с²", "кг·м/с^2", "Н/(м·с)", "км/ч", "мкФ", "kJ".
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

Dim = tuple[int, int, int, int, int, int]

DIMLESS: Dim = (0, 0, 0, 0, 0, 0)
L: Dim = (1, 0, 0, 0, 0, 0)
M: Dim = (0, 1, 0, 0, 0, 0)
T: Dim = (0, 0, 1, 0, 0, 0)
I: Dim = (0, 0, 0, 1, 0, 0)  # noqa: E741
TH: Dim = (0, 0, 0, 0, 1, 0)
N: Dim = (0, 0, 0, 0, 0, 1)


def dmul(a: Dim, b: Dim) -> Dim:
    return tuple(x + y for x, y in zip(a, b))  # type: ignore[return-value]


def dpow(a: Dim, p: int) -> Dim:
    return tuple(x * p for x in a)  # type: ignore[return-value]


def d(**powers: int) -> Dim:
    """d(L=1, T=-2) -> размерность ускорения."""
    order = ["L", "M", "T", "I", "TH", "N"]
    return tuple(powers.get(k, 0) for k in order)  # type: ignore[return-value]


@dataclass(frozen=True)
class Quantity:
    """Множитель к СИ и размерность. 1 км = Quantity(1000, L)."""

    factor: float
    dim: Dim

    def __mul__(self, other: Quantity) -> Quantity:
        return Quantity(self.factor * other.factor, dmul(self.dim, other.dim))

    def __truediv__(self, other: Quantity) -> Quantity:
        return Quantity(self.factor / other.factor, dmul(self.dim, dpow(other.dim, -1)))

    def __pow__(self, p: int) -> Quantity:
        return Quantity(self.factor**p, dpow(self.dim, p))


ONE = Quantity(1.0, DIMLESS)

# Единицы, к которым можно приписывать приставки.
_PREFIXABLE: dict[str, Quantity] = {
    # русские
    "м": Quantity(1, L),
    "г": Quantity(1e-3, M),
    "с": Quantity(1, T),
    "Н": Quantity(1, d(L=1, M=1, T=-2)),
    "Дж": Quantity(1, d(L=2, M=1, T=-2)),
    "Вт": Quantity(1, d(L=2, M=1, T=-3)),
    "Па": Quantity(1, d(L=-1, M=1, T=-2)),
    "В": Quantity(1, d(L=2, M=1, T=-3, I=-1)),
    "А": Quantity(1, I),
    "Ом": Quantity(1, d(L=2, M=1, T=-3, I=-2)),
    "Кл": Quantity(1, d(T=1, I=1)),
    "Ф": Quantity(1, d(L=-2, M=-1, T=4, I=2)),
    "Гц": Quantity(1, d(T=-1)),
    "Тл": Quantity(1, d(M=1, T=-2, I=-1)),
    "Гн": Quantity(1, d(L=2, M=1, T=-2, I=-2)),
    "К": Quantity(1, TH),
    "моль": Quantity(1, N),
    "л": Quantity(1e-3, d(L=3)),
    "эВ": Quantity(1.602176634e-19, d(L=2, M=1, T=-2)),
    # латинские
    "m": Quantity(1, L),
    "g": Quantity(1e-3, M),
    "s": Quantity(1, T),
    "N": Quantity(1, d(L=1, M=1, T=-2)),
    "J": Quantity(1, d(L=2, M=1, T=-2)),
    "W": Quantity(1, d(L=2, M=1, T=-3)),
    "Pa": Quantity(1, d(L=-1, M=1, T=-2)),
    "V": Quantity(1, d(L=2, M=1, T=-3, I=-1)),
    "A": Quantity(1, I),
    "Ohm": Quantity(1, d(L=2, M=1, T=-3, I=-2)),
    "Ω": Quantity(1, d(L=2, M=1, T=-3, I=-2)),
    "C": Quantity(1, d(T=1, I=1)),
    "F": Quantity(1, d(L=-2, M=-1, T=4, I=2)),
    "Hz": Quantity(1, d(T=-1)),
    "T": Quantity(1, d(M=1, T=-2, I=-1)),
    "H": Quantity(1, d(L=2, M=1, T=-2, I=-2)),
    "K": Quantity(1, TH),
    "mol": Quantity(1, N),
    "L": Quantity(1e-3, d(L=3)),
    "l": Quantity(1e-3, d(L=3)),
    "eV": Quantity(1.602176634e-19, d(L=2, M=1, T=-2)),
}

# Единицы без приставок (точное совпадение).
_PLAIN: dict[str, Quantity] = {
    "мин": Quantity(60, T),
    "ч": Quantity(3600, T),
    "сут": Quantity(86400, T),
    "т": Quantity(1000, M),
    "атм": Quantity(101325, d(L=-1, M=1, T=-2)),
    "рад": ONE,
    "°": Quantity(math.pi / 180, DIMLESS),
    "град": Quantity(math.pi / 180, DIMLESS),
    "°C": Quantity(1, TH),  # разность температур
    "°С": Quantity(1, TH),  # кириллическая С
    "min": Quantity(60, T),
    "h": Quantity(3600, T),
    "t": Quantity(1000, M),
    "atm": Quantity(101325, d(L=-1, M=1, T=-2)),
    "rad": ONE,
    "deg": Quantity(math.pi / 180, DIMLESS),
}

_PREFIXES: dict[str, float] = {
    # русские
    "Г": 1e9,
    "М": 1e6,
    "к": 1e3,
    "д": 1e-1,
    "с": 1e-2,
    "м": 1e-3,
    "мк": 1e-6,
    "н": 1e-9,
    "п": 1e-12,
    # латинские
    "G": 1e9,
    "M": 1e6,
    "k": 1e3,
    "d": 1e-1,
    "c": 1e-2,
    "m": 1e-3,
    "u": 1e-6,
    "µ": 1e-6,
    "μ": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
}

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


class UnitError(ValueError):
    pass


def lookup_unit(name: str) -> Quantity:
    """Найти одну единицу по имени, с учётом приставок."""
    if name in _PLAIN:
        return _PLAIN[name]
    if name in _PREFIXABLE:
        return _PREFIXABLE[name]
    # сначала длинные приставки ("мк" раньше "м")
    for prefix in sorted(_PREFIXES, key=len, reverse=True):
        if name.startswith(prefix):
            base = name[len(prefix) :]
            if base in _PREFIXABLE:
                q = _PREFIXABLE[base]
                return Quantity(q.factor * _PREFIXES[prefix], q.dim)
    raise UnitError(f"Неизвестная единица: «{name}»")


_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<name>°[CС]?|[A-Za-zА-Яа-яЁёΩµμ]+)"
    r"|(?P<pow>\^\s*\(?\s*-?\d+\s*\)?|\*\*\s*-?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)"
    r"|(?P<op>[*/·⋅×()])"
    r")"
)


def _tokenize(s: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    s = s.strip()
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m or m.end() == pos:
            raise UnitError(f"Не удалось разобрать единицы: «{s}»")
        kind = m.lastgroup
        assert kind is not None
        tokens.append((kind, m.group(kind)))
        pos = m.end()
        # пробел между двумя единицами = умножение ("Н м")
    return tokens


def _parse_pow(tok: str) -> int:
    t = tok.translate(_SUPERSCRIPTS)
    t = t.replace("^", "").replace("*", "").replace("(", "").replace(")", "").strip()
    return int(t)


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.t = tokens
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> tuple[str, str]:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expr(self) -> Quantity:
        q = self.factor()
        while True:
            tok = self.peek()
            if tok is None or tok == ("op", ")"):
                return q
            if tok[0] == "op" and tok[1] == "/":
                self.take()
                q = q / self.factor()
            elif tok[0] == "op" and tok[1] in "*·⋅×":
                self.take()
                q = q * self.factor()
            elif tok[0] == "name" or tok == ("op", "("):
                q = q * self.factor()  # неявное умножение: "Н м"
            else:
                raise UnitError("Неожиданный символ в единицах")

    def factor(self) -> Quantity:
        tok = self.peek()
        if tok is None:
            raise UnitError("Единицы обрываются")
        if tok == ("op", "("):
            self.take()
            q = self.expr()
            if self.peek() != ("op", ")"):
                raise UnitError("Не хватает закрывающей скобки")
            self.take()
        elif tok[0] == "name":
            self.take()
            q = lookup_unit(tok[1])
        else:
            raise UnitError("Ожидалась единица измерения")
        nxt = self.peek()
        if nxt is not None and nxt[0] == "pow":
            self.take()
            q = q ** _parse_pow(nxt[1])
        return q


def parse_unit(s: str | None) -> Quantity:
    """Разобрать строку единиц в множитель к СИ и размерность. Пустая строка = безразмерно."""
    if s is None or not s.strip():
        return ONE
    s = s.strip()
    if s in _PLAIN or s in _PREFIXABLE:
        return lookup_unit(s)
    tokens = _tokenize(s)
    p = _Parser(tokens)
    q = p.expr()
    if p.peek() is not None:
        raise UnitError(f"Не удалось разобрать единицы: «{s}»")
    return q


_DIM_NAMES: dict[Dim, str] = {
    DIMLESS: "безразмерная величина",
    L: "длина",
    M: "масса",
    T: "время",
    TH: "температура",
    I: "сила тока",
    N: "количество вещества",
    d(L=1, T=-1): "скорость",
    d(L=1, T=-2): "ускорение",
    d(L=1, M=1, T=-2): "сила",
    d(L=2, M=1, T=-2): "энергия (работа, теплота)",
    d(L=2, M=1, T=-3): "мощность",
    d(L=-1, M=1, T=-2): "давление",
    d(L=2): "площадь",
    d(L=3): "объём",
    d(L=-3, M=1): "плотность",
    d(L=1, M=1, T=-1): "импульс",
    d(T=-1): "частота",
    d(L=2, M=1, T=-3, I=-1): "напряжение",
    d(L=2, M=1, T=-3, I=-2): "сопротивление",
    d(T=1, I=1): "заряд",
    d(M=1, T=-2): "жёсткость",
}


def describe_dim(dim: Dim) -> str:
    """Человеческое название размерности, например «скорость»."""
    if dim in _DIM_NAMES:
        return _DIM_NAMES[dim]
    names = ["м", "кг", "с", "А", "К", "моль"]
    parts = [f"{n}^{p}" if p != 1 else n for n, p in zip(names, dim) if p != 0]
    return "величина с размерностью " + "·".join(parts)
