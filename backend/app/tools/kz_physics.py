"""Казахстанские олимпиады по физике (cdn.bc-pf.org): задачи С рисунками и графиками.

Условия и официальные решения лежат в паре PDF (…-tasks.pdf и …-sol.pdf с одним началом имени). Рисунки
вырезаются из PDF условий, ответ берётся из официальных решений и перепроверяется моделями — как для IZhO
(app/tools/izho_physics.py). Задачи, которые уже есть в банке (тот же год, этап, класс и номер), не трогаются.

Запуск из папки backend:
    python -m app.tools.kz_physics --budget 2 --dry-run
    python -m app.tools.kz_physics --budget 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from ..bank import STAGE_NAMES, closed_reason
from ..config import settings
from ..importer import ImportError_
from ..llm import usage_cost
from .izho_physics import _client, import_pair


def _pairs() -> list[tuple[dict, str, str, int | None, str]]:
    """(запись манифеста, адрес условий, адрес решений, класс, метка файла) без повторов."""
    out, seen = [], set()
    for f in sorted((Path(settings.data_dir) / "imports").glob("kz-*physics*.json")):
        for e in json.loads(f.read_text(encoding="utf-8")):
            if e.get("subject") != "physics":
                continue
            for u in e["urls"]:
                m = re.match(r"(.*)-(tasks|sol)\.pdf$", u)
                if not m:
                    continue
                base = m.group(1)
                if (e["slug"], e["year"], base) in seen:
                    continue
                seen.add((e["slug"], e["year"], base))
                g = re.search(r"phys(\d+)", base)
                grade = int(g.group(1)) if g else e.get("grade")
                r = re.search(r"phys\d*-(\d+)$", base)
                out.append((e, f"{base}-tasks.pdf", f"{base}-sol.pdf", grade, f"-r{r.group(1)}" if r else ""))
    return out


async def main_async(args) -> int:
    client = _client()
    total = 0
    try:
        for e, tasks, sol, grade, tag in _pairs():
            if closed_reason(e["olympiad"]):
                continue
            name = f"{e['slug']} {e['year']} {grade or '-'} кл. {tag}"
            if args.dry_run:  # без запросов к моделям и без записи: только список пар файлов
                print(f"{name}: {tasks} + {sol}")
                continue
            if usage_cost() >= args.budget:
                print(f"{name}: пропущен — бюджет исчерпан")
                continue
            title = f"{STAGE_NAMES[e['stage']].lower()} олимпиады «{e['olympiad']}»"
            try:
                rep = await import_pair(
                    client,
                    olympiad=e["olympiad"],
                    slug=e["slug"],
                    stage=e["stage"],
                    year=e["year"],
                    grade=grade,
                    tasks_url=tasks,
                    sol_url=sol,
                    title=title,
                    budget=args.budget,
                    dry_run=False,
                    cache_name="kz-phys",
                    replace_old=False,
                    tag=tag,
                )
            except ImportError_ as exc:  # пары нет (одного из файлов нет на сайте)
                print(f"{name}: нет пары файлов — {str(exc)[:100]}")
                continue
            except Exception as exc:  # один файл не должен ронять весь импорт
                print(f"{name}: ошибка — {type(exc).__name__}: {str(exc)[:160]}")
                continue
            total += len(rep.added)
            print(
                f"{name}: добавлено {len(rep.added)}, не подтверждено {len(rep.dropped)}, пропущено {rep.skipped}"
            )
    finally:
        await client.close()
    print(f"\nВсего добавлено: {total}\nРасход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kz_physics")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    ap.add_argument("--dry-run", action="store_true", help="только показать пары файлов")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
