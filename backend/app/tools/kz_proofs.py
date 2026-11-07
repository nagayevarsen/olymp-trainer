"""Казахстанские олимпиады по математике (cdn.bc-pf.org): задачи с официальными решениями как доказательства.

Берёт манифесты data/imports/kz-*math*.json, у которых в urls лежат PDF решений (*-sol.pdf: в них есть и условия).
Модель только переносит условие и официальное решение, ничего не решает. Задачи, которые уже есть в банке
(то же условие), пропускаются — прежний импорт брал из этих файлов только задачи с числовым ответом.

Запуск из папки backend:
    python -m app.tools.kz_proofs --budget 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ..bank import STAGE_NAMES, closed_reason
from ..config import settings
from ..llm import usage_cost
from .euler_proofs import import_files
from .izho_physics import _client


def _entries() -> list[dict]:
    out = []
    for f in sorted((Path(settings.data_dir) / "imports").glob("kz-*math*.json")):
        for e in json.loads(f.read_text(encoding="utf-8")):
            if (
                e.get("subject") == "math"
                and e.get("grade")
                and all(u.endswith("-sol.pdf") for u in e["urls"])
            ):
                out.append(e)
    return out


async def main_async(args) -> int:
    client = _client()
    total = 0
    try:
        for e in _entries():
            if closed_reason(e["olympiad"]):
                continue
            name = f"{e['slug']} {e['year']} {e['grade']} кл."
            if usage_cost() >= args.budget:
                print(f"{name}: пропущен — бюджет исчерпан")
                continue
            title = f"{STAGE_NAMES[e['stage']].lower()} олимпиады «{e['olympiad']}», {e['grade']} класс"
            try:
                added, dropped = await import_files(
                    client,
                    e["olympiad"],
                    e["slug"],
                    e["stage"],
                    e["year"],
                    e["grade"],
                    e["urls"],
                    title,
                    "kz-proofs",
                )
            except Exception as exc:
                print(f"{name}: ошибка — {type(exc).__name__}: {str(exc)[:160]}")
                continue
            total += len(added)
            print(f"{name}: добавлено {len(added)}" + (f"; отброшено {len(dropped)}" if dropped else ""))
    finally:
        await client.close()
    print(f"\nВсего добавлено: {total}\nРасход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kz_proofs")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
