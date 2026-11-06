"""ИИ-функции: лестница подсказок, построение шаблонов для клонов,
перекрёстная проверка вариантов другой моделью."""

from __future__ import annotations

from pydantic import ValidationError

from .bank import Hints, Problem, Template, Verification
from .checker import AnswerKey, check_answer
from .cloner import make_variant, verify_template
from .config import settings
from .llm import LLMError, complete_json

SUBJECT_RU = {"math": "математика", "physics": "физика"}

HINTS_SYSTEM = """Ты опытный тренер школьников по олимпиадной {subject}.
Твоя цель — научить решать, а не выдать ответ. Пиши по-русски, коротко и понятно
для ученика 7–9 класса. Формулы пиши в LaTeX внутри $...$."""

HINTS_PROMPT = """Задача ({topic}):
{statement}

Официальный ответ: {answer}

Составь лестницу из 3 подсказок по возрастанию силы:
1. Намёк: на что обратить внимание (не раскрывая идею).
2. Ключевая идея решения.
3. План решения по шагам, без итоговых вычислений.
Затем полное решение с ответом.

Важно: в подсказках 1–3 не используй конкретные числа из условия — они должны
подходить и для вариантов задачи с другими числами.

Честность: решение должно честно приводить к официальному ответу, каждый шаг — обоснован.
Не подгоняй вычисления под ответ и не пропускай шаги, которые не можешь обосновать. Если полностью
обосновать решение не получается — так и напиши в решении («здесь нужен шаг, который я не смог
строго обосновать: …»), а не выдумывай.

Верни JSON: {{"steps": ["...", "...", "..."], "solution": "..."}}"""


async def generate_hints(problem: Problem) -> tuple[Hints, str]:
    answer = f"{problem.answer.value:g} {problem.answer.unit or ''}".strip()
    data, model = await complete_json(
        HINTS_PROMPT.format(topic=problem.topic, statement=problem.statement, answer=answer),
        HINTS_SYSTEM.format(subject=SUBJECT_RU[problem.subject]),
    )
    try:
        return Hints.model_validate(data), model
    except ValidationError as exc:
        raise LLMError(f"Модель вернула подсказки в неверном формате: {exc}") from exc


TEMPLATE_SYSTEM = """Ты помогаешь превращать олимпиадные задачи в параметрические шаблоны,
чтобы генерировать варианты с другими числами. Отвечай только JSON."""

TEMPLATE_PROMPT = """Задача:
{statement}

Официальный ответ: {answer}

Сделай шаблон:
- "text": условие, где изменяемые числа заменены на {{имя}} (латиница, например {{v}}, {{m1}}).
  Остальной текст оставь как в оригинале.
- "params": для каждого имени диапазон {{"min":..,"max":..,"step":..}} разумных значений,
  или {{"value":..}} если число менять нельзя (например g = 10).
- "original": значения параметров в оригинальной задаче.
- "solver": Python-код функции solve(<параметры>) -> число, которая вычисляет ответ
  {unit_note}. Без import и без math. — доступны sqrt, sin, cos, tan, pi, log, exp,
  floor, ceil, gcd, lcm, comb, factorial, range, min, max, abs, round, sum, pow.
  НЕ округляй итоговый ответ в solve: система сама проверяет, что ответ «красивый».
- "constraints": список Python-выражений, которые должны быть истинны, чтобы задача
  имела смысл (можно использовать параметры и answer), например "answer > 0", "v1 != v2".
- "answer_integer": true, если ответ по смыслу задачи должен быть целым.

Если задачу нельзя параметризовать (доказательство, ответ не число, смысл ломается
при смене чисел), верни {{"parametrizable": false, "reason": "..."}}."""


async def build_template(problem: Problem) -> tuple[Template | None, list[str]]:
    """Попросить модель сделать шаблон и проверить его. Возвращает (шаблон или None, журнал)."""
    log: list[str] = []
    unit_note = f"в единицах «{problem.answer.unit}»" if problem.answer.unit else "(безразмерное число)"
    answer = f"{problem.answer.value:g} {problem.answer.unit or ''}".strip()
    for chain_start in range(min(3, len(settings.llm_chain))):
        chain = settings.llm_chain[chain_start:]
        try:
            data, model = await complete_json(
                TEMPLATE_PROMPT.format(statement=problem.statement, answer=answer, unit_note=unit_note),
                TEMPLATE_SYSTEM,
                chain=chain,
            )
        except LLMError as exc:
            log.append(f"Модели недоступны: {exc}")
            return None, log
        if data.get("parametrizable") is False:
            log.append(f"{model}: задачу нельзя параметризовать — {data.get('reason')}")
            return None, log
        data.pop("parametrizable", None)
        try:
            template = Template.model_validate(data)
        except ValidationError as exc:
            log.append(f"{model}: шаблон в неверном формате: {exc.errors()[:2]}")
            continue
        try:
            report = verify_template(problem, template)
        except Exception as exc:  # SandboxError и пр.
            log.append(f"{model}: решатель не прошёл проверку: {exc}")
            continue
        if not report.ok:
            log.append(f"{model}: шаблон не прошёл проверку: {report.errors}")
            continue
        template.verification = Verification(reproduces_original=True, checked_by=[model])
        log.append(f"{model}: шаблон воспроизводит официальный ответ ✓")
        return template, log
    return None, log


CROSS_SYSTEM = """Ты сильный олимпиадник. Реши задачу внимательно и верни только JSON."""
CROSS_PROMPT = """{statement}

Реши задачу. Верни JSON: {{"answer": "<ответ числом{unit_hint}>"}}"""


async def cross_check(problem: Problem, seeds: tuple[int, ...] = (1, 2)) -> tuple[bool, list[str]]:
    """Независимая проверка: другая модель решает варианты, ответы сверяются с решателем."""
    assert problem.template is not None
    log: list[str] = []
    unit_hint = f" с единицами {problem.answer.unit}" if problem.answer.unit else ""
    agree = 0
    for seed in seeds:
        variant = make_variant(problem, seed)
        try:
            data, model = await complete_json(
                CROSS_PROMPT.format(statement=variant.statement, unit_hint=unit_hint),
                CROSS_SYSTEM,
                chain=settings.crosscheck_chain,
            )
        except LLMError as exc:
            log.append(f"seed={seed}: модели недоступны ({exc})")
            continue
        result = check_answer(
            AnswerKey(
                variant.answer.value, variant.answer.unit, rel_tol=0.02 if variant.answer.unit else 1e-9
            ),
            str(data.get("answer", "")),
        )
        log.append(
            f"seed={seed}: {model} ответил {data.get('answer')!r}, решатель {variant.answer.value:g}"
            f" → {'совпало' if result.correct else 'НЕ совпало'}"
        )
        agree += result.correct
    return agree == len(seeds), log
