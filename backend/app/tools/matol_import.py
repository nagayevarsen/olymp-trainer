"""Импорт задач с matol.kz (Смагуловская и др.), где у задач нет официальных ответов.

Ответ получаем проверкой (app/verify.py): три независимых решения моделями разных производителей
плюс две программы, при споре подключается Sonnet. В банк идёт только задача, ответ которой прошёл
проверку; у неё answer.origin = "verified" и verified_by — чем подтверждён.

Запуск из папки backend:
    python -m app.tools.matol_import --node 527 511 --olympiad "Олимпиада им. Шалтая Смагулова" \\
        --slug smagulov --stage city --budget 1.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from html import unescape

from .. import verify
from ..bank import Problem, closed_reason, load_bank, problems_dir
from ..importer import _get
from ..llm import LLMError, complete_json, usage_cost

BASE = "https://matol.kz"

PRECHECK_SYSTEM = "Ты сортируешь олимпиадные задачи. Отвечай только JSON."
PRECHECK_PROMPT = """Задача:
{statement}

Ответь JSON:
{{"numeric": true, если у задачи один итоговый ответ — одно число (а не доказательство, пример,
   несколько ответов, «да/нет», формула или описание конструкции); иначе false,
 "self_contained": true, если условие понятно без рисунка и без других задач,
 "kind": "enumeration" | "graph_plot" | "graph_theory" | "other" (перебор / графики функций / графы / прочее),
 "topic": "тема по-русски 1–2 слова",
 "title": "короткое название по-русски, 2–4 слова"}}"""


def olympiad_pages(node: int) -> tuple[str, list[tuple[str, str]]]:
    """Название сезона и страницы туров (адрес, «6 класс, 1 тур»). Командные туры пропускаются."""
    html = _get(f"{BASE}/nodes/{node}").text
    active = re.search(r'<li class="active">([^<]+)</li>', html)
    season = unescape(active.group(1)).strip() if active else ""
    pages = []
    for href, text in re.findall(r'href="(/olympiads/\d+)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"\s+", " ", unescape(re.sub("<[^>]+>", "", text))).strip()
        if "команд" in text.lower():
            continue
        pages.append((BASE + href, text))
    return season, pages


def page_problems(url: str) -> list[tuple[int, str, bool]]:
    """(номер, условие, есть ли картинка) для каждой задачи страницы тура."""
    html = _get(url).text
    out = []
    for num, body in re.findall(r"<b>Задача №(\d+)\.</b>(.*?)<a href=\"/comments/", html, re.S):
        has_img = "<img" in body
        text = re.sub(r"<br\s*/?>", "\n", body)
        text = re.sub(r"\s*\n\s*", "\n", unescape(re.sub("<[^>]+>", "", text))).strip()
        out.append((int(num), text.replace("\xa0", " "), has_img))
    return out


def season_year(season: str) -> int | None:
    m = re.search(r"(20\d\d)\s*-\s*(20\d\d)", season)
    if m:
        return int(m.group(2))
    m = re.search(r"\((20\d\d)\s*год", season)  # «26-я олимпиада (2026 год)»
    return int(m.group(1)) if m else None


async def import_problem(meta: dict, num: int, statement: str, log: list[str]) -> Problem | None:
    try:
        pre, _ = await complete_json(
            PRECHECK_PROMPT.format(statement=statement), PRECHECK_SYSTEM, chain=["anthropic:claude-haiku-5-5"]
        )
    except LLMError as exc:
        log.append(f"сортировка не удалась: {exc}")
        return None
    if not pre.get("numeric") or not pre.get("self_contained"):
        log.append("не числовой ответ или нужен рисунок — пропуск")
        return None
    kind = pre.get("kind") if pre.get("kind") in verify.METHOD else "other"
    v = await verify.verify_answer(statement, None, kind=kind)
    log.extend(v.log())
    if not v.accepted or v.answer is None:
        return None
    pid = f"{meta['slug']}-{meta['year']}-math{meta['grade'] or ''}-t{meta['tour']}-{num}"
    raw = {
        "id": pid,
        "subject": "math",
        "topic": str(pre.get("topic") or "Разное")[:40],
        "title": str(pre.get("title") or f"Задача {num}")[:60],
        "statement": statement,
        "answer": {"value": float(v.answer), "origin": "verified", "verified_by": v.verified_by},
        "source": {
            "olympiad": meta["olympiad"],
            "year": meta["year"],
            "stage": meta["stage"],
            **({"grade": meta["grade"]} if meta["grade"] else {}),
            "number": num,
            "url": meta["url"],
        },
    }
    return Problem.model_validate(raw)


async def main_async(args) -> int:
    existing = set(load_bank())
    sem = asyncio.Semaphore(args.parallel)
    stats = {"added": 0, "rejected": 0, "skipped_img": 0, "budget": 0}
    jobs = []
    for node in args.node:
        season, pages = olympiad_pages(node)
        year = season_year(season)
        for url, label in pages:
            g = re.search(r"(\d+)\s*класс", label)
            t = re.search(r"(\d+)\s*тур", label)
            meta = {
                "olympiad": args.olympiad,
                "slug": args.slug,
                "stage": args.stage,
                "year": year,
                "grade": int(g.group(1)) if g else None,
                "tour": t.group(1) if t else "1",
                "url": url,
            }
            for num, statement, has_img in page_problems(url):
                if has_img:
                    stats["skipped_img"] += 1
                    continue
                jobs.append((meta, num, statement))
    print(f"Задач-кандидатов: {len(jobs)}", flush=True)

    async def one(meta: dict, num: int, statement: str) -> None:
        async with sem:
            if usage_cost() >= args.budget:
                stats["budget"] += 1
                return
            pid_prefix = f"{meta['slug']}-{meta['year']}-math{meta['grade'] or ''}-t{meta['tour']}-{num}"
            if pid_prefix in existing:
                return
            log: list[str] = []
            p = await import_problem(meta, num, statement, log)
        if p:
            (problems_dir() / f"{p.id}.json").write_text(
                json.dumps(p.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            stats["added"] += 1
        else:
            stats["rejected"] += 1
        head = f"{'✓' if p else '✗'} {meta['year']} {meta['grade']} кл, тур {meta['tour']}, №{num}"
        print(head + " | " + " | ".join(log[-2:])[:200], flush=True)

    await asyncio.gather(*(one(*j) for j in jobs))
    print(
        f"\nДобавлено: {stats['added']}, отклонено: {stats['rejected']}, с картинкой: {stats['skipped_img']}, "
        f"не успели по бюджету: {stats['budget']}"
    )
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="matol_import")
    ap.add_argument("--node", type=int, nargs="+", required=True, help="узлы сезонов на matol.kz (nodes/N)")
    ap.add_argument("--olympiad", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--stage", default="city")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    ap.add_argument("--parallel", type=int, default=3)
    args = ap.parse_args(argv)
    if reason := closed_reason(args.olympiad):
        print(f"Олимпиада закрыта для Казахстана, импорт не запущен: {reason}", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
