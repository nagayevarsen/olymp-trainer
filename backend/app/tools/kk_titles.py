"""Перевод названий задач и тем банка на казахский → frontend/src/titles.kk.json.

Условия и разборы не переводятся (остаются на языке источника); переводятся только короткие названия
задач и темы, которые видны в списках. Уже переведённое не пересчитывается, запуск можно повторять.

Запуск из папки backend:
    python -m app.tools.kk_titles --budget 0.5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from ..config import settings
from ..llm import usage_cost
from .izho_physics import HAIKU, _ask, _client

OUT = Path(__file__).resolve().parents[3] / "frontend" / "src" / "titles.kk.json"
BATCH = 80
SYSTEM = """Ты переводишь короткие названия олимпиадных задач по математике и физике и названия тем
с русского на казахский. Используй принятые в казахстанских школах термины. Числа, формулы, латинские
буквы и имена собственные не меняй. Отвечай только JSON-объектом: тот же набор ключей, значения — перевод."""


async def translate(client, items: dict[str, str]) -> dict[str, str]:
    prompt = "Переведи значения на казахский:\n" + json.dumps(items, ensure_ascii=False)
    out = await _ask(client, HAIKU, SYSTEM, [{"type": "text", "text": prompt}], max_tokens=8000)
    return {k: str(v).strip() for k, v in out.items() if k in items and str(v).strip()}


async def main_async(budget: float) -> int:
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"titles": {}, "topics": {}}
    titles: dict[str, str] = {}
    topics: dict[str, str] = {}
    for f in sorted((Path(settings.data_dir) / "problems").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("title"):
            titles[d["id"]] = d["title"]
        for part in re.split(r"[,;]", str(d.get("topic") or "")):
            if part.strip():
                topics[part.strip().lower()] = part.strip().lower()
    todo = {k: v for k, v in titles.items() if k not in done["titles"]}
    todo_t = {k: v for k, v in topics.items() if k not in done["topics"]}
    jobs = [("titles", dict(list(todo.items())[i : i + BATCH])) for i in range(0, len(todo), BATCH)]
    jobs += [("topics", dict(list(todo_t.items())[i : i + BATCH])) for i in range(0, len(todo_t), BATCH)]
    client = _client()
    sem = asyncio.Semaphore(4)

    async def run(kind: str, items: dict[str, str]) -> None:
        async with sem:
            if usage_cost() >= budget:
                return
            try:
                done[kind].update(await translate(client, items))
            except Exception as exc:  # одна пачка не должна ронять остальные
                print(f"пачка {kind} пропущена: {type(exc).__name__}: {str(exc)[:100]}")

    try:
        await asyncio.gather(*(run(k, i) for k, i in jobs))
    finally:
        await client.close()
    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"названий: {len(done['titles'])}/{len(titles)}, тем: {len(done['topics'])}/{len(topics)}")
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kk_titles")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    return asyncio.run(main_async(ap.parse_args(argv).budget))


if __name__ == "__main__":
    sys.exit(main())
