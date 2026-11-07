"""Импорт задач олимпиады им. Эйлера (8 класс) как задач на доказательство: все этапы и годы с matol.ru.

Модель только переносит условие и официальное решение из PDF решений (в них есть и условия) — ничего не
решает и не придумывает. Ученик сдаёт решение, его оценивает Sonnet по официальному решению
(app/grading.py). Задачи, уже лежащие в банке (то же условие), пропускаются.

Запуск из папки backend:
    python -m app.tools.euler_proofs --stage final --years 2019 --budget 0.2
    python -m app.tools.euler_proofs --all --budget 2
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import re
import sys
from pathlib import Path

from ..bank import Problem, closed_reason, figures_dir, load_bank, problems_dir
from ..importer import ImportError_, fetch_pdf
from ..llm import usage_cost
from .izho_physics import _ask, _client, _pdf_block

OLYMPIAD = "Олимпиада им. Леонарда Эйлера"
B = "https://www.matol.ru/files/"
MODEL = "claude-haiku-5-5"
MIN_SOLUTION = 150
STAGE_WORDS = {
    "distance": "заочного (дистанционного) этапа",
    "region": "регионального этапа",
    "final": "заключительного этапа",
}


def _zip(name: str, *members: str) -> list[str]:
    return [f"{B}{name}#member={m}" for m in members]


# Файлы решений с matol.ru/archives.php: (этап, год) -> адреса PDF.
FILES: dict[tuple[str, int], list[str]] = {}
# Заочный: Disttur{тур}_{ГГ}_sol.pdf — сезон ГГ/ГГ+1, год олимпиады ГГ+1 (как в уже загруженных задачах).
for yy in range(12, 23):
    FILES[("distance", 2000 + yy + 1)] = [
        f"{B}Disttur{t}_{yy}_sol.pdf" for t in ((1, 2, 3, 4) if yy < 14 else (1, 2, 3))
    ]
FILES[("distance", 2024)] = [B + "Disttur1_23_sol.pdf", B + "Disttur2_23sol.pdf", B + "Disttur3_23sol.pdf"]
FILES[("distance", 2025)] = [f"{B}Disttur{t}_24_sol.pdf" for t in (1, 2, 3)]
FILES[("distance", 2026)] = [B + "Disttur1_25sol+crit+comm.pdf", B + "Disttur2_25sol.pdf"]
for y in range(2013, 2022):
    FILES[("final", y)] = [f"{B}3etap{y}sol.pdf"]
FILES[("final", 2022)] = [B + "3etap2022 day1 sol.pdf", B + "3etap2022 day2 sol.pdf"]
FILES[("final", 2023)] = [B + "3etap2023_day1_sol.pdf", B + "3etap2023_day2_sol.pdf"]
FILES[("final", 2024)] = _zip("3etap2024.zip", "3etap2024day1sol.pdf", "3etap2024day2sol.pdf")
FILES[("final", 2025)] = _zip("3etap2025.zip", "3etap2025day1sol.pdf", "3etap2025day2sol.pdf")
FILES[("final", 2026)] = [B + "3etap2026day1sol.pdf", B + "3etap2026day2sol.pdf"]
FILES[("region", 2013)] = [B + "Euler_reg_12-13_sol.pdf"]
FILES[("region", 2014)] = [B + "Euler_reg_13-14_sol.pdf"]
FILES[("region", 2018)] = [B + "Euler2018_reg_sol_day_1.pdf", B + "Euler2018_reg_sol_day_2.pdf"]
FILES[("region", 2019)] = [B + "Euler2019_reg_day_1_sol.pdf", B + "Euler2019_reg_day_2_sol.pdf"]
FILES[("region", 2020)] = [B + "8klass2020_2etap_sol.pdf"]
for y in (2021, 2022, 2023):
    FILES[("region", y)] = [f"{B}8 klass{y}_2 etap_day{d}_sol.pdf" for d in (1, 2)]
FILES[("region", 2024)] = [B + "8 klass2024_2 etap_sol.pdf"]
FILES[("region", 2025)] = [B + "8_klass2025_2_etap_sol.pdf"]
FILES[("region", 2026)] = [B + "8_klass2026_2_etap_day1_sol.pdf", B + "8_klass2026_2_etap_day2_sol.pdf"]

SYSTEM = """Ты аккуратно переносишь олимпиадные задачи по математике из официальных PDF в базу данных.
Ничего не придумывай и не решай сам: условие и решение — только из файлов. Отвечай только JSON."""

PROMPT = """Это официальные решения {title} {year} года
(файлы по порядку: {files}). В них есть условия и решения задач.

Для каждой задачи верни:
- "file": номер файла (с 1), где эта задача;
- "number": номер задачи в этом файле;
- "title": короткое название по-русски (2–4 слова); "topic": тема по-русски (1–2 слова:
  «Арифметика», «Геометрия», «Комбинаторика», «Теория чисел», «Алгебра», «Логика»…);
- "statement": условие дословно на русском, формулы в LaTeX внутри $...$;
- "solution": официальное решение полностью, без сокращений, формулы в LaTeX внутри $...$; если в файле
  несколько решений — первое; если решение опирается на рисунок — опиши рисунок словами;
- "complete": true, только если и условие, и решение перенесены целиком и ничего не пропущено.

Задачи для других классов, критерии оценивания и комментарии жюри пропусти.
Если одна и та же задача есть в нескольких файлах — верни её один раз.
JSON: {{"problems": [ ... ]}}"""


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", s.lower())[:200]


def _write(problem: Problem) -> None:
    data = problem.model_dump(mode="json", exclude_none=True)
    (problems_dir() / f"{problem.id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _is_duplicate(statement: str, known: list[str]) -> bool:
    key = _norm(statement)
    return any(difflib.SequenceMatcher(None, key, k).ratio() > 0.8 for k in known)


async def import_group(client, stage: str, year: int) -> tuple[list[str], list[str]]:
    title = f"{STAGE_WORDS[stage]} олимпиады имени Леонарда Эйлера, 8 класс"
    return await import_files(
        client, OLYMPIAD, f"euler-{stage}", stage, year, 8, FILES[(stage, year)], title, "euler-proofs"
    )


async def import_files(
    client,
    olympiad: str,
    slug: str,
    stage: str,
    year: int,
    grade: int | None,
    files: list[str],
    title: str,
    cache_dir: str,
) -> tuple[list[str], list[str]]:
    """Перенести задачи и официальные решения из PDF как задачи на доказательство."""
    cache = Path(figures_dir()).parent / "raw" / cache_dir / f"{slug}-{year}-{grade or 0}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    urls, pdfs = [], []
    for u in files:
        try:
            pdfs.append(fetch_pdf(u))
            urls.append(u)
        except ImportError_ as exc:  # одного файла нет — берём остальные
            print(f"  пропущен файл: {str(exc)[:120]}")
    if not urls:
        raise ImportError_("ни один файл не скачался")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        content = [_pdf_block(p) for p in pdfs]
        names = ", ".join(u.rsplit("/", 1)[-1] for u in urls)
        content.append({"type": "text", "text": PROMPT.format(title=title, year=year, files=names)})
        data = await _ask(client, MODEL, SYSTEM, content)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    same_year = [p for p in load_bank().values() if p.source.olympiad == olympiad and p.source.year == year]
    known = [_norm(p.statement) for p in same_year]
    used = {
        p.source.number
        for p in same_year
        if p.source.stage == stage and p.source.grade == grade and p.source.number
    }
    added, dropped = [], []
    for item in data.get("problems", []):
        statement = str(item.get("statement") or "").strip()
        solution = str(item.get("solution") or "").strip()
        if not item.get("complete") or not statement or len(solution) < MIN_SOLUTION:
            dropped.append(f"{item.get('file')}/{item.get('number')}: неполное условие или решение")
            continue
        if _is_duplicate(statement, known):
            continue
        n = next(i for i in range(1, 1000) if i not in used)
        try:
            file_i = max(1, min(len(urls), int(item.get("file") or 1)))
        except (TypeError, ValueError):
            file_i = 1
        try:
            problem = Problem(
                id=f"{slug}-{year}-math{grade or ''}-{n}",
                subject="math",
                topic=str(item.get("topic") or "Олимпиадная математика")[:40],
                title=str(item.get("title") or f"Задача {n}")[:60],
                statement=statement,
                answer={"proof": True},
                solution=solution,
                source={
                    "olympiad": olympiad,
                    "year": year,
                    "stage": stage,
                    "grade": grade,
                    "number": n,
                    "url": urls[file_i - 1],
                },
            )
        except Exception as exc:  # негодная запись не должна ронять импорт
            dropped.append(f"{item.get('file')}/{item.get('number')}: {str(exc)[:120]}")
            continue
        _write(problem)
        used.add(n)
        known.append(_norm(statement))
        added.append(problem.id)
    return added, dropped


async def main_async(args) -> int:
    if closed_reason(OLYMPIAD):
        print("Олимпиада закрыта для Казахстана", file=sys.stderr)
        return 2
    keys = sorted(FILES, key=lambda k: (k[1], k[0]))
    if not args.all:
        keys = [k for k in keys if k[0] in args.stage and k[1] in args.years]
    client = _client()
    total = 0
    try:
        for stage, year in keys:
            if usage_cost() >= args.budget:
                print(f"{stage} {year}: пропущен — бюджет исчерпан")
                continue
            try:
                added, dropped = await import_group(client, stage, year)
            except Exception as exc:
                print(f"{stage} {year}: ошибка — {type(exc).__name__}: {str(exc)[:200]}")
                continue
            total += len(added)
            print(f"{stage} {year}: добавлено {len(added)}" + (f"; отброшено: {dropped}" if dropped else ""))
    finally:
        await client.close()
    print(f"\nВсего добавлено: {total}\nРасход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="euler_proofs")
    ap.add_argument("--stage", nargs="*", default=["distance", "region", "final"])
    ap.add_argument("--years", type=int, nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
