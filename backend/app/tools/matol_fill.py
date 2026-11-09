"""Дозагрузка пропущенных задач городских этапов с matol.kz (Смагулова, городская Жаутыковская).

matol_import берёт только задачи с числовым ответом, который подтвердили несколько моделей. Остальные
(доказательства, «могло ли», построения) он пропускал. Здесь они добавляются как задачи на доказательство:
решение составляет Sonnet, вторая модель (Haiku) его проверяет; не прошедшие проверку не берутся.
Задачи с картинкой и числовые без подтверждённого ответа не добавляются. В решение вписано, что оно
составлено ИИ и не официальное.

Число задач на странице источника записывается в data/official_counts.json (адрес страницы → сколько задач),
по нему сайт показывает, полный ли вариант олимпиады в банке.

Запуск из папки backend:
    python -m app.tools.matol_fill --budget 3 --parallel 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from ..bank import Problem, load_bank, problems_dir
from ..config import settings
from ..importer import _get
from ..llm import LLMError, complete_json, usage_cost
from .matol_import import (
    BASE,
    PRECHECK_PROMPT,
    PRECHECK_SYSTEM,
    olympiad_pages,
    page_problems,
    season_year,
)

OLYMPIADS = {
    "Олимпиада им. Шалтая Смагулова": ("smagulov", "city"),
    "Городская Жаутыковская олимпиада (Алматы)": ("zhaut-city", "city"),
}
KNOWN_NODES = [525, 514, 504, 492, 491, 527, 511]
SEASON_INDEX = [111, 157]  # узлы matol.kz со списком сезонов: городская Жаутыковская, Смагулова
NOTE = "Решение составлено ИИ и не является официальным."

SOLVE_SYSTEM = (
    "Ты сильный тренер по олимпиадной математике. Решай строго, без пропусков. Отвечай только JSON."
)
SOLVE_PROMPT = """Задача:
{statement}

Дай полное строгое решение для школьника (ответ и доказательство или пример). Если задачу нельзя строго решить
по условию, ответ неоднозначен или условие неполное — верни {{"solved": false}}.
Верни JSON: {{"solved": true, "solution": "…", "topic": "тема 1–2 слова", "title": "название 2–4 слова"}}.
Формулы в LaTeX внутри $...$."""
CHECK_SYSTEM = "Ты строгий жюри олимпиады. Отвечай только JSON."
CHECK_PROMPT = """Задача:
{statement}

Предложенное решение:
{solution}

Проверь: решение верное, полное и ничего не пропускает? Верни JSON: {{"ok": true или false, "reason": "кратко"}}."""


def counts_path() -> Path:
    return Path(settings.data_dir) / "official_counts.json"


def find_nodes(bank) -> list[int]:
    """Сезоны городских олимпиад: узлы matol.kz по адресам страниц, уже лежащим в банке, плюс известные."""
    nodes = set(KNOWN_NODES)
    for index in SEASON_INDEX:  # страницы-списки всех сезонов олимпиады
        try:
            html = _get(f"{BASE}/nodes/{index}").text
        except Exception:  # noqa: BLE001
            continue
        for node, label in re.findall(r'href="/nodes/(\d+)"[^>]*>([^<]*)', html):
            if "олимпиада" in label and ("год)" in label or "у.г.)" in label):
                nodes.add(int(node))
    urls = {
        p.source.url
        for p in bank.values()
        if p.source.olympiad in OLYMPIADS and p.source.url and "matol.kz/olympiads/" in p.source.url
    }
    for url in sorted(urls):
        try:
            html = _get(url).text
        except Exception:  # noqa: BLE001 — страница недоступна: пропускаем, остальные найдутся
            continue
        for node, label in re.findall(r'href="/nodes/(\d+)"[^>]*>([^<]*)', html):
            if "год)" in label:
                nodes.add(int(node))
    return sorted(nodes)


def olympiad_of(node_html: str) -> str | None:
    if "Смагулов" in node_html:
        return "Олимпиада им. Шалтая Смагулова"
    if "Жаутыковская" in node_html:
        return "Городская Жаутыковская олимпиада (Алматы)"
    return None


async def fill_one(meta: dict, num: int, statement: str, sem, stats: dict, budget: float) -> None:
    pid = f"{meta['slug']}-{meta['year']}-math{meta['grade'] or ''}-t{meta['tour']}-{num}"
    async with sem:
        if usage_cost() >= budget:
            stats["budget"] += 1
            return
        try:
            pre, _ = await complete_json(
                PRECHECK_PROMPT.format(statement=statement),
                PRECHECK_SYSTEM,
                chain=["anthropic:claude-haiku-5-5"],
            )
            if pre.get("numeric") or not pre.get("self_contained"):
                stats["skip_numeric_or_unclear"] += 1
                return
            sol, _ = await complete_json(
                SOLVE_PROMPT.format(statement=statement), SOLVE_SYSTEM, chain=["anthropic:claude-sonnet-5-5"]
            )
            if not sol.get("solved") or len(str(sol.get("solution", ""))) < 30:
                stats["unsolved"] += 1
                return
            chk, _ = await complete_json(
                CHECK_PROMPT.format(statement=statement, solution=sol["solution"]),
                CHECK_SYSTEM,
                chain=["anthropic:claude-haiku-5-5"],
            )
        except LLMError as exc:
            stats["error"] += 1
            print("✗", pid, str(exc)[:80], flush=True)
            return
    if not chk.get("ok"):
        stats["rejected"] += 1
        print("✗", pid, "проверка не прошла:", str(chk.get("reason"))[:100], flush=True)
        return
    raw = {
        "id": pid,
        "subject": "math",
        "topic": str(pre.get("topic") or sol.get("topic") or "Разное")[:40],
        "title": str(sol.get("title") or pre.get("title") or f"Задача {num}")[:60],
        "statement": statement,
        "answer": {
            "origin": "verified",
            "verified_by": ["решение составлено Sonnet, проверено Haiku"],
            "proof": True,
        },
        "solution": f"{NOTE} {sol['solution']}",
        "source": {
            "olympiad": meta["olympiad"],
            "year": meta["year"],
            "stage": meta["stage"],
            **({"grade": meta["grade"]} if meta["grade"] else {}),
            "number": num,
            "url": meta["url"],
        },
    }
    p = Problem.model_validate(raw)
    (problems_dir() / f"{p.id}.json").write_text(
        json.dumps(p.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stats["added"] += 1
    print("✓", pid, round(usage_cost(), 3), flush=True)


async def main_async(args) -> int:
    bank = load_bank()
    existing = set(bank)
    nodes = find_nodes(bank)
    print("узлы:", nodes, flush=True)
    sem = asyncio.Semaphore(args.parallel)
    stats = {
        "added": 0,
        "rejected": 0,
        "unsolved": 0,
        "skip_numeric_or_unclear": 0,
        "img": 0,
        "error": 0,
        "budget": 0,
    }
    counts: dict[str, int] = {}
    jobs = []
    for node in nodes:
        try:
            season, pages = olympiad_pages(node)
            node_html = _get(f"{BASE}/nodes/{node}").text
        except Exception as exc:  # noqa: BLE001
            print("узел", node, "недоступен:", str(exc)[:60], flush=True)
            continue
        name = olympiad_of(node_html)
        if not name:
            continue
        slug, stage = OLYMPIADS[name]
        year = season_year(season)
        for url, label in pages:
            g = re.search(r"(\d+)\s*класс", label)
            t = re.search(r"(\d+)\s*тур", label)
            meta = {
                "olympiad": name,
                "slug": slug,
                "stage": stage,
                "year": year,
                "grade": int(g.group(1)) if g else None,
                "tour": t.group(1) if t else "1",
                "url": url,
            }
            items = page_problems(url)
            counts[url] = len(items)
            for num, statement, has_img in items:
                pid = f"{slug}-{year}-math{meta['grade'] or ''}-t{meta['tour']}-{num}"
                if pid in existing:
                    continue
                if has_img:
                    stats["img"] += 1
                    continue
                jobs.append((meta, num, statement))
    counts_path().write_text(
        json.dumps(counts, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"страниц: {len(counts)}, пропущенных задач без картинки: {len(jobs)}", flush=True)
    await asyncio.gather(*(fill_one(*j, sem, stats, args.budget) for j in jobs))
    print("\nитог:", stats)
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="matol_fill")
    ap.add_argument("--budget", type=float, default=2.0, help="остановиться при таком расходе Claude, $")
    ap.add_argument("--parallel", type=int, default=3)
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
