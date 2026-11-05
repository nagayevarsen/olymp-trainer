"""Проверка ответа задачи, у которой нет официального ответа.

Идея: ответу одной модели верить нельзя, особенно в задачах на перебор и с графиками —
там ИИ ошибается чаще всего. Поэтому ответ принимается, только если сошлись независимые способы:

1. Тип задачи определяет модель: перебор/подсчёт вариантов, графики функций, графы, прочее.
2. Три модели разных производителей решают задачу рассуждением, не видя ответов друг друга.
3. Две разные модели пишут программу, которая находит ответ вычислением, а не «в уме»:
   - для перебора — полный перебор по определению из условия, без выведенных формул;
   - для графиков — численный счёт по точкам/сетке (корни, пересечения, экстремумы, площади);
   - для графов — перебор всех вершин/рёбер/раскрасок на маленьком графе из условия.
   Программы выполняются в песочнице (sandbox.py), обе должны дать одно число.
4. Если дешёвые модели не договорились, подключается модель на ступень выше (Sonnet):
   её решение и её программа добавляются как ещё два голоса, правило применяется заново.
5. Правило принятия:
   - для «рискованных» типов (перебор, графики, графы) — обе программы совпали между собой
     и с ответом большинства моделей (не меньше двух из трёх);
   - для остальных — все три модели согласны и хотя бы одна программа это подтверждает.
   Иначе ответ отклоняется — задача в банк не идёт.

Перед массовым использованием правило калибруется на задачах с официальным ответом:
`bank_tool verify-eval` — ответы прячутся, проверка запускается вслепую и сравнивается с ключом.
"""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field

from .llm import LLMError, complete_json
from .methods import METHODS, catalog_text, helper_code
from .sandbox import BRUTE_FORCE_TIMEOUT_S, SandboxError, run_solver

RISKY_KINDS = {"enumeration", "graph_plot", "graph_theory"}

# Модели разных производителей: ошибки у них меньше коррелируют.
SOLVER_MODELS = [
    "anthropic:claude-haiku-5-5",
    "gemini:gemini-3.5-flash",
    "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free",
]
# Программы пишут модели двух разных производителей (Gemini — запасной вариант).
PROGRAM_MODELS = ["anthropic:claude-haiku-5-5", "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free"]
# Модель «на ступень выше». Зовётся только если дешёвые модели не договорились:
# её решение и её программа — дополнительные голоса, а не решающий.
ESCALATION_MODEL = "anthropic:claude-sonnet-5-5"
# Запасные модели, если основная недоступна (у бесплатных моделей маленькие квоты).
FALLBACK = {
    "gemini:gemini-3.5-flash": [
        "gemini:gemini-3.8-flash",
        "gemini:gemini-flash-latest",
        "openrouter:google/gemma-4-31b-it:free",
    ],
    "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free": [
        "openrouter:google/gemma-4-31b-it:free",
        "gemini:gemini-3.8-flash",
        "gemini:gemini-3.5-flash",
    ],
    "anthropic:claude-haiku-5-5": [],
    "anthropic:claude-sonnet-5-5": [],
}

CLASSIFY_SYSTEM = "Ты классифицируешь олимпиадные задачи. Отвечай только JSON."
CLASSIFY_PROMPT = """Задача:
{statement}

Определи тип задачи:
- "enumeration" — ответ можно найти полным перебором конечного числа вариантов
  (сколько способов, сколько чисел с условием, наименьшее/наибольшее число, расстановки, игры,
  клетчатые доски, цифры, делимость с небольшим диапазоном);
- "graph_plot" — нужно работать с графиком функции или зависимости: точки пересечения, число корней,
  экстремумы, площадь под графиком, чтение зависимости x(t), v(t) и т. п.;
- "graph_theory" — графы: вершины, рёбра, пути, турниры, знакомства, раскраски;
- "other" — остальное (алгебра, геометрия с вычислением, физика по формулам).

Верни JSON: {{"kind": "...", "reason": "коротко почему"}}"""

SOLVE_SYSTEM = """Ты сильный олимпиадник. Реши задачу внимательно, проверь ответ подстановкой
и проверкой крайних случаев. Отвечай только JSON."""
SOLVE_PROMPT = """{statement}

Реши задачу. Верни JSON:
{{"answer": <итоговый ответ одним числом{unit_hint}>, "solution": "краткое решение, 2–6 предложений"}}
Если ответ не одно число — {{"answer": null}}."""

PROGRAM_SYSTEM = """Ты пишешь короткие проверочные программы на ограниченном Python. Отвечай только JSON."""
PROGRAM_RULES = """Ограничения языка (программа запускается в песочнице):
- одна функция solve() без аргументов, возвращает одно число;
- нельзя: import, while, классы, lambda, методы и атрибуты (никаких .append, .add, .sort, math.),
  словари, try, global;
- можно: for, if, break, continue, вложенные функции, списки и множества через генераторы,
  срезы, range, len, sum, min, max, abs, round, int, float, str, list, tuple, set, sorted,
  reversed, enumerate, zip, all, any, divmod, pow, gcd, lcm, isqrt, sqrt, sin, cos, tan, atan, atan2,
  log, exp, floor, ceil, factorial, comb, pi, permutations, combinations,
  combinations_with_replacement, product (как в itertools);
- вместо lst.append(x) пиши lst = lst + [x]; вместо s.add(x) — s = s | {{x}};
- время работы не больше 20 секунд (примерно до 10^7 простых операций)."""
PROGRAM_PROMPT = """Задача:
{statement}

{method}

{rules}

Верни JSON: {{"feasible": true, "code": "def solve():\\n    ..."}}
Если честно посчитать вычислением нельзя (слишком большой перебор, нужен рисунок) —
{{"feasible": false, "reason": "..."}}."""

LARGE = """
ЕСЛИ ЧИСЛА СЛИШКОМ БОЛЬШИЕ ДЛЯ ПЕРЕБОРА (больше ~10^7 вариантов), действуй так:
1) обобщи задачу: замени большое число параметром n (2026 → n);
2) напиши функцию brute(n), которая решает задачу ПЕРЕБОРОМ для маленьких n;
3) возьми подходящий метод из банка ниже (или свою формулу) и напиши formula(n);
4) в solve() проверь formula(n) == brute(n) для всех маленьких n, где перебор быстрый
   (не меньше 5 значений). Если хоть одно не совпало — верни -123456789;
5) иначе верни formula(большое число).
Функции из банка можно вызывать по имени — их код подставится автоматически.

Банк проверенных методов:
{catalog}"""

FIX_PROMPT = """Твоя прошлая программа:
{code}

не запустилась: {error}
Исправь её, соблюдая ограничения:
{rules}
Верни JSON в том же формате."""

METHOD = {
    "enumeration": """Напиши программу ПОЛНОГО ПЕРЕБОРА, которая находит ответ прямо по определению из условия:
перебери все объекты (числа, расстановки, раскраски, ходы) и проверь условие задачи для каждого.
НЕ используй выведенные формулы и «хитрые» соображения — только перебор и проверку условия.
Если в условии большие числа (например 2026), но перебор всё равно укладывается во время — перебирай.
"""
    + "{large}",
    "graph_plot": """Напиши программу, которая находит ответ ЧИСЛЕННО, без аналитических выкладок:
задай функцию/зависимость из условия, пройди по мелкой сетке значений и найди нужное —
корни и пересечения по смене знака (с уточнением делением пополам через for),
экстремумы по сравнению соседних значений, площади методом трапеций с мелким шагом.
Ответ округли так, как требует условие.""",
    "graph_theory": """Напиши программу ПОЛНОГО ПЕРЕБОРА для графа из условия: перебери все подмножества рёбер,
все раскраски, все пути или все турниры (что требует условие) и проверь условие для каждого.
Не используй теоремы — только перебор. Если граф в общем случае большой, но в условии конкретный
и маленький — перебирай его.
"""
    + "{large}",
    "other": """Напиши программу, которая вычисляет ответ по шагам решения, а затем ПРОВЕРЯЕТ его:
подставь найденные значения обратно во все условия задачи. Если проверка не сходится,
верни -123456789. Для физики ответ — в тех единицах, которые просит условие.""",
}


@dataclass
class Attempt:
    model: str
    answer: float | None
    note: str = ""


@dataclass
class Verdict:
    accepted: bool
    answer: float | None
    kind: str
    reasoning: list[Attempt] = field(default_factory=list)
    programs: list[Attempt] = field(default_factory=list)
    reason: str = ""
    escalated: bool = False

    @property
    def verified_by(self) -> list[str]:
        out = [f"решение: {a.model} → {fmt(a.answer)}" for a in self.reasoning if a.answer is not None]
        out += [
            f"программа ({self.kind}): {a.model} → {fmt(a.answer)}"
            for a in self.programs
            if a.answer is not None
        ]
        return out

    def log(self) -> list[str]:
        lines = [f"тип: {self.kind}" + (" (подключена модель сильнее)" if self.escalated else "")]
        lines += [f"решение {a.model}: {fmt(a.answer)} {a.note}".rstrip() for a in self.reasoning]
        lines += [f"программа {a.model}: {fmt(a.answer)} {a.note}".rstrip() for a in self.programs]
        lines.append(("ПРИНЯТ " + fmt(self.answer)) if self.accepted else f"ОТКЛОНЁН: {self.reason}")
        return lines


def fmt(x: float | None) -> str:
    if x is None:
        return "—"
    return str(int(x)) if float(x).is_integer() else f"{x:.6g}"


def same(a: float | None, b: float | None, rel_tol: float) -> bool:
    if a is None or b is None or math.isnan(a) or math.isnan(b):
        return False
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=1e-9)


def _num(x) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, str):
        try:
            v = float(x.replace(",", ".").replace(" ", "").replace("−", "-"))
        except ValueError:
            return None
        return v if math.isfinite(v) else None
    return None


async def _ask(model: str, prompt: str, system: str) -> tuple[dict, str]:
    return await complete_json(prompt, system, chain=[model, *FALLBACK.get(model, [])])


async def classify(statement: str, model: str = SOLVER_MODELS[0]) -> str:
    try:
        data, _ = await _ask(model, CLASSIFY_PROMPT.format(statement=statement), CLASSIFY_SYSTEM)
    except LLMError:
        return "other"
    kind = str(data.get("kind", "other"))
    return kind if kind in METHOD else "other"


async def solve_by_reasoning(statement: str, model: str, unit: str | None) -> Attempt:
    unit_hint = f" в единицах {unit}" if unit else ""
    try:
        data, used = await _ask(
            model, SOLVE_PROMPT.format(statement=statement, unit_hint=unit_hint), SOLVE_SYSTEM
        )
    except LLMError as exc:
        return Attempt(model, None, f"(недоступна: {str(exc)[:80]})")
    return Attempt(used, _num(data.get("answer")))


def with_helpers(code: str) -> str:
    """Подставить код методов из банка, которые программа вызывает, но не определяет сама."""
    extra = [
        helper_code(m)
        for m in METHODS
        if re.search(rf"\b{m['id']}\s*\(", code) and not re.search(rf"def\s+{m['id']}\s*\(", code)
    ]
    return "\n".join([*extra, code])


def run_program(code: str) -> tuple[float | None, str]:
    code = with_helpers(code)
    try:
        res = run_solver(code, [{}], timeout=BRUTE_FORCE_TIMEOUT_S)[0]
    except SandboxError as exc:
        return None, f"(код отклонён/упал: {str(exc)[:80]})"
    if not res.get("ok"):
        return None, f"(ошибка: {str(res.get('error'))[:80]})"
    v = res["answer"]
    if v == -123456789:
        return None, "(подстановка не сошлась)"
    return (v if math.isfinite(v) else None), ""


async def solve_by_program(statement: str, model: str, kind: str) -> Attempt:
    method = METHOD[kind].replace("{large}", LARGE.format(catalog=catalog_text()))
    prompt = PROGRAM_PROMPT.format(statement=statement, method=method, rules=PROGRAM_RULES)
    try:
        data, used = await _ask(model, prompt, PROGRAM_SYSTEM)
    except LLMError as exc:
        return Attempt(model, None, f"(недоступна: {str(exc)[:80]})")
    if not data.get("feasible") or not isinstance(data.get("code"), str):
        return Attempt(used, None, f"(не стала считать: {str(data.get('reason', ''))[:80]})")
    value, note = await asyncio.to_thread(run_program, data["code"])
    if value is None and note.startswith(("(код отклонён", "(ошибка")):
        # Одна попытка исправить: показываем модели её код и ошибку.
        fix = FIX_PROMPT.format(code=data["code"], error=note.strip("()"), rules=PROGRAM_RULES)
        try:
            data2, used = await _ask(used, prompt + "\n\n" + fix, PROGRAM_SYSTEM)
        except LLMError:
            return Attempt(used, None, note)
        if data2.get("feasible") and isinstance(data2.get("code"), str):
            value, note2 = await asyncio.to_thread(run_program, data2["code"])
            note = note2 or "(исправлена после ошибки)"
    return Attempt(used, value, note)


def decide(
    kind: str, reasoning: list[Attempt], programs: list[Attempt], rel_tol: float
) -> tuple[bool, float | None, str]:
    """Правило принятия ответа. Чистая функция — её проверяют тесты.

    Ответ X принимается, если:
    - перебор/графики/графы: X дали не меньше двух программ, против X — не больше одной программы
      (и только когда программ три), решений за X не меньше двух и больше, чем против;
    - остальное: решений за X не меньше трёх, против — не больше одного (и только когда решений
      больше трёх), хотя бы одна программа дала X и ни одна не дала другое число.
    """
    votes = [a.answer for a in reasoning if a.answer is not None]
    progs = [a.answer for a in programs if a.answer is not None]

    def count(x: float, xs: list[float]) -> int:
        return sum(same(x, y, rel_tol) for y in xs)

    if kind in RISKY_KINDS:
        if len(progs) < 2:
            return False, None, "для этого типа нужны две программы, сработало меньше"
        ans = max(progs, key=lambda x: count(x, progs))
        pro, contra = count(ans, progs), len(progs) - count(ans, progs)
        if pro < 2:
            return False, None, "программы разошлись: " + ", ".join(fmt(p) for p in progs)
        if contra > 1 or (contra == 1 and len(progs) < 3):
            return False, None, "программы разошлись: " + ", ".join(fmt(p) for p in progs)
        v_pro = count(ans, votes)
        if v_pro < 2 or v_pro <= len(votes) - v_pro:
            return False, None, f"программы дали {fmt(ans)}, решения: " + ", ".join(fmt(v) for v in votes)
        return True, ans, ""

    if len(votes) < 3:
        return False, None, "нужны три независимых решения, получено меньше"
    ans = max(votes, key=lambda x: count(x, votes))
    v_pro = count(ans, votes)
    v_contra = len(votes) - v_pro
    if v_pro < 3 or v_contra > 1 or (v_contra == 1 and len(votes) <= 3):
        return False, None, "решения разошлись: " + ", ".join(fmt(v) for v in votes)
    if not progs:
        return False, None, "ни одна программа не подтвердила ответ"
    if any(not same(ans, p, rel_tol) for p in progs):
        return False, None, "программа дала другой ответ: " + ", ".join(fmt(p) for p in progs)
    return True, ans, ""


async def verify_answer(
    statement: str, unit: str | None = None, kind: str | None = None, escalate: bool = True
) -> Verdict:
    kind = kind or await classify(statement)
    rel_tol = 0.01 if unit else 1e-6
    reasoning, programs = await asyncio.gather(
        asyncio.gather(*(solve_by_reasoning(statement, m, unit) for m in SOLVER_MODELS)),
        asyncio.gather(*(solve_by_program(statement, m, kind) for m in PROGRAM_MODELS)),
    )
    reasoning, programs = list(reasoning), list(programs)
    ok, ans, reason = decide(kind, reasoning, programs, rel_tol)
    escalated = False
    if not ok and escalate:
        # Дешёвые модели не договорились — зовём модель сильнее (решение + программа).
        escalated = True
        extra_r, extra_p = await asyncio.gather(
            solve_by_reasoning(statement, ESCALATION_MODEL, unit),
            solve_by_program(statement, ESCALATION_MODEL, kind),
        )
        reasoning.append(extra_r)
        programs.append(extra_p)
        ok, ans, reason = decide(kind, reasoning, programs, rel_tol)
    return Verdict(ok, ans, kind, reasoning, programs, reason, escalated)
