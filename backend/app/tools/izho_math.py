"""Импорт задач IZhO по математике как задач на доказательство (условие + официальное решение, izho.kz).

На IZhO почти все задачи на доказательство, итогового числа у них нет. Модель только переносит условие
и официальное решение из PDF решений (там есть и условия) — ничего не решает и не придумывает.
Ученик сдаёт доказательство, его оценивает Sonnet по официальному решению (app/grading.py).
Задачи, которые уже есть в банке (тот же год и номер), пропускаются.

Запуск из папки backend:
    python -m app.tools.izho_math --years 2019 --budget 0.2
    python -m app.tools.izho_math --all --budget 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ..bank import Problem, closed_reason, figures_dir, load_bank, problems_dir
from ..importer import fetch_pdf
from ..llm import usage_cost
from .izho_physics import _ask, _client, _pdf_block

OLYMPIAD = "Международная Жаутыковская олимпиада (IZhO)"
B = "https://izho.kz/wp-content/uploads/"
# Официальные решения по математике (в них есть и условия). Источник — архив izho.kz/contest/problems/.
FILES = {
    2010: ["2018/12/izho10_sol.pdf"],
    2011: ["2018/12/izho11_1day_rus_sol.pdf", "2018/12/izho11_2day_rus_sol.pdf"],
    2012: ["2018/12/izho12_rus_sol.pdf"],
    2013: ["2018/12/Reshenie-1den-final.pdf", "2018/12/Reshenie-2-den-final.pdf"],
    2014: ["2018/12/solrus.pdf"],
    2015: ["2018/01/1day_rus_sol.pdf", "2018/01/2day_rus_sol.pdf"],
    2016: ["2018/01/day1sol.pdf", "2018/01/day2sol.pdf"],
    2018: ["2018/01/Resheniya-Rus-1-den.pdf", "2018/01/Resheniya-Rus-2-den.pdf"],
    2019: ["2019/01/day_1_sol_rus.pdf", "2019/01/day_2_sol_rus.pdf"],
    2020: ["2020/01/day_1_solutions.pdf", "2020/01/day_2_solutions.pdf"],
    2021: ["2021/01/Resheniya-zadach-MZHO-2021.pdf"],
    2022: ["2022/02/1.day_1_sol_rus.pdf", "2022/02/MATH_day_2_sol_rus.pdf"],
    2023: ["2023/02/Day_1_sol_2023.pdf", "2023/02/Day_2_sol_2023.pdf"],
    2024: ["2024/12/Day_1_sol_2024.pdf", "2024/12/Day_2_sol_2024.pdf"],
}
MODEL = "claude-haiku-5-5"
MIN_SOLUTION = 200  # короче — скорее всего, это не полное официальное решение

SYSTEM = """Ты аккуратно переносишь олимпиадные задачи по математике из официальных PDF в базу данных.
Ничего не придумывай и не решай сам: условие и решение — только из файлов. Отвечай только JSON."""

PROMPT = """Это официальные решения математического тура Международной Жаутыковской олимпиады {year} года
(файлы по порядку: {files}). В них есть условия и решения задач 1–6.

Для каждой задачи верни:
- "number": номер задачи (1–6);
- "file": номер файла (с 1), где эта задача;
- "title": короткое название по-русски (2–4 слова); "topic": тема по-русски (1–2 слова:
  «Неравенства», «Геометрия», «Комбинаторика», «Теория чисел», «Алгебра», «Функциональные уравнения»…);
- "statement": условие дословно, на русском (если файл на английском — точный перевод), формулы в LaTeX
  внутри $...$;
- "solution": официальное решение полностью, без сокращений, на русском, формулы в LaTeX внутри $...$;
  если в файле несколько решений — первое; если решение опирается на рисунок — опиши рисунок словами;
- "complete": true, только если и условие, и решение перенесены целиком и ничего не пропущено.

Если одна и та же задача есть в нескольких файлах — верни её один раз.
JSON: {{"problems": [ ... ]}}"""


def _existing(year: int) -> set[int]:
    return {
        p.source.number
        for p in load_bank().values()
        if p.source.olympiad == OLYMPIAD and p.subject == "math" and p.source.year == year and p.source.number
    }


def _write(problem: Problem) -> None:
    data = problem.model_dump(mode="json", exclude_none=True)
    (problems_dir() / f"{problem.id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


async def import_year(client, year: int) -> tuple[list[str], list[str]]:
    urls = [B + f for f in FILES[year]]
    pdfs = [fetch_pdf(u) for u in urls]
    cache = Path(figures_dir()).parent / "raw" / "izho-math" / f"{year}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        content = [_pdf_block(p) for p in pdfs]
        content.append({"type": "text", "text": PROMPT.format(year=year, files=", ".join(FILES[year]))})
        data = await _ask(client, MODEL, SYSTEM, content)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    have = _existing(year)
    added, dropped = [], []
    for item in data.get("problems", []):
        try:
            n = int(item["number"])
        except (KeyError, TypeError, ValueError):
            dropped.append("без номера")
            continue
        if n in have:
            continue
        statement = str(item.get("statement") or "").strip()
        solution = str(item.get("solution") or "").strip()
        if not item.get("complete") or not statement or len(solution) < MIN_SOLUTION:
            dropped.append(f"задача {n}: неполное условие или решение")
            continue
        try:
            file_i = max(1, min(len(urls), int(item.get("file") or 1)))
        except (TypeError, ValueError):
            file_i = 1
        try:
            problem = Problem(
                id=f"izho-{year}-math-{n}",
                subject="math",
                topic=str(item.get("topic") or "Олимпиадная математика")[:40],
                title=str(item.get("title") or f"Задача {n}")[:60],
                statement=statement,
                answer={"proof": True},
                solution=solution,
                source={
                    "olympiad": OLYMPIAD,
                    "year": year,
                    "stage": "international",
                    "number": n,
                    "url": urls[file_i - 1],
                },
            )
        except Exception as exc:  # негодная запись не должна ронять импорт
            dropped.append(f"задача {n}: {str(exc)[:120]}")
            continue
        _write(problem)
        have.add(n)
        added.append(problem.id)
    return added, dropped


async def main_async(args) -> int:
    if closed_reason(OLYMPIAD):
        print("Олимпиада закрыта для Казахстана", file=sys.stderr)
        return 2
    years = sorted(FILES) if args.all else args.years
    client = _client()
    total = 0
    try:
        for y in years:
            if usage_cost() >= args.budget:
                print(f"{y}: пропущен — бюджет исчерпан")
                continue
            try:
                added, dropped = await import_year(client, y)
            except Exception as exc:
                print(f"{y}: ошибка — {type(exc).__name__}: {str(exc)[:200]}")
                continue
            total += len(added)
            print(f"{y}: добавлено {len(added)} {added}" + (f"; отброшено: {dropped}" if dropped else ""))
    finally:
        await client.close()
    print(f"\nВсего добавлено: {total}\nРасход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="izho_math")
    ap.add_argument("--years", type=int, nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--budget", type=float, default=0.3, help="остановиться при таком расходе Claude, $")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
