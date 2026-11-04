"""Банк задач: формат JSON-файлов и загрузка.

Каждая задача — отдельный файл data/problems/<id>.json. Формат описан в
docs/PROBLEM_FORMAT.md. Задачи проверяются при загрузке: если файл
написан с ошибкой, сервер сразу скажет, в каком файле и что не так.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .config import settings
from .units import UnitError, parse_unit

Stage = Literal[
    "school",
    "qualifying",
    "distance",
    "district",
    "city",
    "region",
    "republic",
    "final",
    "international",
    "other",
]
Subject = Literal["math", "physics"]

STAGE_NAMES = {
    "school": "Школьный этап",
    "qualifying": "Отборочный этап",
    "distance": "Дистанционный этап",
    "district": "Районный этап",
    "city": "Городской этап",
    "region": "Региональный (областной) этап",
    "republic": "Республиканский этап",
    "final": "Заключительный этап",
    "international": "Международная олимпиада",
    "other": "Другое",
}


class Source(BaseModel):
    olympiad: str = Field(description="Название олимпиады, например «Республиканская олимпиада»")
    year: int | None = None
    stage: Stage = "other"
    grade: int | None = Field(default=None, ge=1, le=12)
    number: int | None = Field(default=None, ge=1, description="Номер задачи в варианте")
    url: str | None = None

    @property
    def track_id(self) -> str:
        """Трек = одна олимпиада + один этап. Задачи разных треков не смешиваются."""
        return hashlib.sha1(f"{self.olympiad}|{self.stage}".encode()).hexdigest()[:10]

    def track_title(self) -> str:
        if self.stage == "other":
            return self.olympiad
        return f"{self.olympiad} — {STAGE_NAMES[self.stage].lower()}"

    def label(self) -> str:
        return ", ".join([self.track_title(), *self._details()])

    def short_label(self) -> str:
        """Без названия олимпиады — для списка внутри одного трека."""
        return ", ".join(self._details())

    def _details(self) -> list[str]:
        parts: list[str] = []
        if self.year:
            parts.append(str(self.year))
        if self.grade:
            parts.append(f"{self.grade} класс")
        if self.number:
            parts.append(f"задача {self.number}")
        return parts


class Answer(BaseModel):
    value: float
    unit: str | None = None
    rel_tol: float | None = Field(
        default=None,
        gt=0,
        lt=0.5,
        description="Допустимая относительная погрешность. По умолчанию: 1% для физики (есть единицы), точно для математики",
    )

    @property
    def tolerance(self) -> float:
        if self.rel_tol is not None:
            return self.rel_tol
        return 0.01 if self.unit else 1e-9

    @field_validator("unit")
    @classmethod
    def unit_must_parse(cls, v: str | None) -> str | None:
        if v:
            try:
                parse_unit(v)
            except UnitError as exc:
                raise ValueError(str(exc)) from exc
        return v


class ParamRange(BaseModel):
    """Параметр задачи: либо фиксированный (value), либо диапазон min..max с шагом step."""

    value: float | None = None
    min: float | None = None
    max: float | None = None
    step: float = 1

    @model_validator(mode="after")
    def check(self) -> ParamRange:
        if self.value is None and (self.min is None or self.max is None):
            raise ValueError("Укажите value или min и max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min больше max")
        if self.step <= 0:
            raise ValueError("step должен быть > 0")
        return self


class Verification(BaseModel):
    reproduces_original: bool = False
    cross_checked: bool = False
    checked_by: list[str] = []
    note: str | None = None


class Template(BaseModel):
    """Шаблон для генерации вариантов задачи («клонов»)."""

    text: str = Field(description="Условие с плейсхолдерами {имя_параметра}")
    params: dict[str, ParamRange]
    original: dict[str, float] = Field(description="Значения параметров в оригинальной задаче")
    solver: str = Field(description="Python-код с функцией solve(**params) -> число")
    constraints: list[str] = Field(default=[], description="Условия на параметры и answer")
    answer_integer: bool = False
    answer_max_decimals: int | None = 2
    verification: Verification = Verification()

    @model_validator(mode="after")
    def check_placeholders(self) -> Template:
        missing = set(self.original) ^ set(self.params)
        if missing:
            raise ValueError(f"original и params должны содержать одни и те же имена: {missing}")
        for name in self.params:
            if "{" + name + "}" not in self.text:
                raise ValueError(f"Параметр {name} не встречается в тексте как {{{name}}}")
        return self


class Hints(BaseModel):
    steps: list[str] = Field(min_length=1, max_length=3)
    solution: str


class Problem(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    subject: Subject
    topic: str
    title: str
    statement: str
    answer: Answer
    source: Source
    points: int | None = Field(default=None, ge=10, le=3000, description="Ручное значение баллов")
    template: Template | None = None
    hints: Hints | None = None
    solution: str | None = Field(default=None, description="Официальное или своё решение")

    @property
    def can_clone(self) -> bool:
        return self.template is not None and self.template.verification.reproduces_original


class BankError(RuntimeError):
    pass


def problems_dir() -> Path:
    return Path(settings.data_dir) / "problems"


def load_problem_file(path: Path) -> Problem:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        problem = Problem.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise BankError(f"Ошибка в файле {path.name}:\n{exc}") from exc
    if problem.id != path.stem:
        raise BankError(f"В файле {path.name} id = «{problem.id}», а должно совпадать с именем файла")
    return problem


@lru_cache(maxsize=1)
def trusted_domains() -> tuple[str, ...]:
    """Домены из data/sources.json — только с них можно брать задачи."""
    path = Path(settings.data_dir) / "sources.json"
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(s["domain"].lower().removeprefix("www.") for s in data["sources"])


def is_trusted_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in trusted_domains())


@lru_cache(maxsize=1)
def load_bank() -> dict[str, Problem]:
    bank: dict[str, Problem] = {}
    for path in sorted(problems_dir().glob("*.json")):
        p = load_problem_file(path)
        if p.source.url and not is_trusted_url(p.source.url):
            raise BankError(
                f"В файле {path.name} источник {p.source.url} не из списка проверенных сайтов "
                "(data/sources.json)"
            )
        bank[p.id] = p
    return bank


def save_problem(problem: Problem) -> None:
    path = problems_dir() / f"{problem.id}.json"
    data = problem.model_dump(mode="json", exclude_none=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_bank.cache_clear()


def get_problem(problem_id: str) -> Problem | None:
    return load_bank().get(problem_id)
