"""Утилита для работы с банком задач.

Запуск из папки backend:

    python -m app.tools.bank_tool check              # проверить все задачи и шаблоны
    python -m app.tools.bank_tool templates          # ИИ делает шаблоны для задач без шаблона
    python -m app.tools.bank_tool templates --id X   # ... только для задачи X (--force — пересоздать)
    python -m app.tools.bank_tool crosscheck         # другая модель решает варианты, сверяем ответы
    python -m app.tools.bank_tool hints              # ИИ пишет подсказки для задач без подсказок
    python -m app.tools.bank_tool preview X          # показать 3 варианта задачи X
    python -m app.tools.bank_tool discover URL       # найти PDF на странице проверенного сайта
    python -m app.tools.bank_tool import-manifest data/imports/kurchatov.json   # импорт по списку
    python -m app.tools.bank_tool verify-eval --sample 30 --risky   # калибровка проверки ответов
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .. import ai
from ..bank import BankError, Problem, load_bank, save_problem
from ..checker import format_number
from ..cloner import CloneError, make_variant, verify_template
from ..llm import LLMError


def _select(ids: list[str] | None) -> list[Problem]:
    bank = load_bank()
    if not ids:
        return list(bank.values())
    missing = [i for i in ids if i not in bank]
    if missing:
        sys.exit(f"Нет задач: {missing}")
    return [bank[i] for i in ids]


def cmd_check(args) -> int:
    try:
        problems = _select(args.id)
    except BankError as exc:
        print(exc)
        return 1
    bad = 0
    for p in problems:
        if not p.template:
            print(f"  {p.id}: без шаблона (варианты недоступны)")
            continue
        report = verify_template(p, p.template)
        flag = p.template.verification.reproduces_original
        status = "✓" if report.ok else "✗"
        print(f"{status} {p.id}: ответ решателя {report.original_answer}, вариантов {report.variants_ok}/3")
        for e in report.errors:
            print(f"     {e}")
        if report.ok != flag:
            if args.fix:
                p.template.verification.reproduces_original = report.ok
                save_problem(p)
                print("     → отметка verification.reproduces_original обновлена")
            else:
                print(f"     ! в файле reproduces_original={flag}, а на деле {report.ok} (запустите с --fix)")
                bad += 1
        if not report.ok:
            bad += 1
    print(f"\nЗадач: {len(problems)}, проблем: {bad}")
    return 1 if bad else 0


async def cmd_templates(args) -> int:
    """Шаблоны для задач без шаблона. --prefix задаёт порядок (сначала задачи с первым префиксом id),
    --parallel — сколько задач одновременно, --budget — остановиться, когда расход Claude превысит сумму."""
    from ..llm import usage_cost

    problems = [p for p in _select(args.id) if args.force or not p.template]
    if args.prefix:
        order = {pref: i for i, pref in enumerate(args.prefix)}

        def rank(p: Problem) -> int:
            return next((i for pref, i in order.items() if p.id.startswith(pref)), len(order))

        problems = sorted((p for p in problems if rank(p) < len(order)), key=lambda p: (rank(p), p.id))
    print(f"Задач без шаблона: {len(problems)}", flush=True)
    sem = asyncio.Semaphore(getattr(args, "parallel", 1) or 1)
    done = {"ok": 0, "fail": 0, "skipped": 0}

    async def one(p: Problem) -> None:
        async with sem:
            if args.budget and usage_cost() >= args.budget:
                done["skipped"] += 1
                return
            template, log = await ai.build_template(p)
        if template:
            p.template = template
            save_problem(p)
            done["ok"] += 1
        else:
            done["fail"] += 1
        print(f"{'✓' if template else '✗'} {p.id}: {log[-1] if log else ''}"[:220], flush=True)

    await asyncio.gather(*(one(p) for p in problems))
    print(f"\nШаблонов: {done['ok']}, не вышло: {done['fail']}, пропущено по бюджету: {done['skipped']}")
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


async def cmd_crosscheck(args) -> int:
    for p in _select(args.id):
        if not p.can_clone:
            continue
        print(f"→ {p.id}")
        ok, log = await ai.cross_check(p)
        for line in log:
            print(f"     {line}")
        assert p.template is not None
        p.template.verification.cross_checked = ok
        models = {line.split(": ")[1].split(" ")[0] for line in log if "ответил" in line}
        p.template.verification.checked_by = sorted(set(p.template.verification.checked_by) | models)
        save_problem(p)
        print(f"     перекрёстная проверка: {'✓' if ok else '✗'}")
    return 0


async def cmd_hints(args) -> int:
    for p in _select(args.id):
        if p.hints and not args.force:
            continue
        print(f"→ {p.id}: пишу подсказки…")
        try:
            hints, model = await ai.generate_hints(p)
        except LLMError as exc:
            print(f"     ошибка: {exc}")
            continue
        p.hints = hints
        save_problem(p)
        print(f"     сохранено ({model}) ✓ — проверьте текст вручную!")
    return 0


def cmd_preview(args) -> int:
    p = _select([args.problem])[0]
    print(f"Оригинал: {p.statement}\nОтвет: {format_number(p.answer.value)} {p.answer.unit or ''}\n")
    for seed in range(1, 4):
        try:
            v = make_variant(p, seed)
        except CloneError as exc:
            print(f"seed={seed}: {exc}")
            continue
        print(f"Вариант seed={seed}: {v.statement}")
        print(f"Ответ: {format_number(v.answer.value)} {v.answer.unit or ''}\n")
    return 0


def cmd_discover(args) -> int:
    from ..importer import discover

    for url in discover(args.url, args.pattern):
        print(url)
    return 0


async def cmd_import_manifest(args) -> int:
    """Манифест — JSON-список партий: {olympiad, stage, year, subject, slug, grade?, urls: [...]}."""
    import json
    from pathlib import Path

    from ..importer import import_pdf

    batches = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    total_added = 0
    sem = asyncio.Semaphore(args.parallel)

    async def one(b: dict, url: str) -> None:
        nonlocal total_added
        async with sem:
            rep = await import_pdf(
                url,
                olympiad=b["olympiad"],
                stage=b["stage"],
                year=b["year"],
                subject=b["subject"],
                slug=b["slug"],
                grade=b.get("grade"),
                dry_run=args.dry_run,
            )
        total_added += len(rep.added)
        skipped = ", ".join(f"{k}: {v}" for k, v in rep.skipped.items())
        status = rep.error or f"найдено {rep.found}, добавлено {len(rep.added)} ({rep.model})"
        print(
            f"{b['slug']} {b['year']} {url.rsplit('/', 1)[-1]}: {status}"
            + (f" | пропущено — {skipped}" if skipped else ""),
            flush=True,
        )

    await asyncio.gather(*(one(b, url) for b in batches for url in b["urls"]))
    load_bank.cache_clear()
    print(f"\nВсего добавлено: {total_added}")
    from ..llm import USAGE, usage_cost

    for model, u in USAGE.items():
        print(
            f"{model}: запросов {u['calls']}, токенов вход {u['input']}, выход {u['output']}, "
            f"${u['cost_micro'] / 1e6:.4f}"
        )
    if USAGE:
        print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


async def cmd_verify_eval(args) -> int:
    """Калибровка verify.py: прячем официальный ответ, проверяем вслепую, сравниваем с ключом."""
    import random

    from .. import verify
    from ..llm import USAGE, usage_cost

    pool = [p for p in load_bank().values() if p.answer.origin == "official" and p.source.url]
    if args.subject:
        pool = [p for p in pool if p.subject == args.subject]
    random.Random(args.seed).shuffle(pool)
    sem = asyncio.Semaphore(args.parallel)
    picked: list[tuple[Problem, str]] = []
    for p in pool:
        if len(picked) >= args.sample:
            break
        kind = await verify.classify(p.statement)
        if args.risky and kind not in verify.RISKY_KINDS:
            continue
        picked.append((p, kind))
    print(f"Задач для проверки: {len(picked)}")
    stats: dict[str, dict[str, int]] = {}

    async def one(p: Problem, kind: str) -> None:
        async with sem:
            v = await verify.verify_answer(
                p.statement, p.answer.unit, kind=kind, escalate=not args.no_escalate
            )
        tol = p.answer.tolerance
        if v.accepted:
            outcome = "верно" if verify.same(v.answer, p.answer.value, max(tol, 1e-6)) else "ОШИБКА"
        else:
            outcome = "отклонено"
        s = stats.setdefault(kind, {"верно": 0, "ОШИБКА": 0, "отклонено": 0, "эскалаций": 0})
        s[outcome] += 1
        s["эскалаций"] += v.escalated
        print(f"\n{p.id}: ключ {verify.fmt(p.answer.value)} → {outcome}")
        for line in v.log():
            print(f"     {line}")

    await asyncio.gather(*(one(p, k) for p, k in picked))
    print("\nИтог по типам:")
    for kind, s in stats.items():
        print(f"  {kind}: {s}")
    for model, u in USAGE.items():
        print(
            f"{model}: запросов {u['calls']}, вход {u['input']}, выход {u['output']}, ${u['cost_micro'] / 1e6:.4f}"
        )
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bank_tool", description="Работа с банком задач")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="проверить банк")
    c.add_argument("--id", nargs="*")
    c.add_argument("--fix", action="store_true", help="обновить отметки проверки в файлах")
    for name in ("templates", "hints", "crosscheck"):
        s = sub.add_parser(name)
        s.add_argument("--id", nargs="*")
        s.add_argument("--force", action="store_true")
        if name == "templates":
            s.add_argument("--prefix", nargs="*", help="порядок: сначала задачи с этими префиксами id")
            s.add_argument("--parallel", type=int, default=1)
            s.add_argument("--budget", type=float, help="остановиться при таком расходе Claude, $")
    pv = sub.add_parser("preview")
    pv.add_argument("problem")
    dc = sub.add_parser("discover", help="найти PDF на странице")
    dc.add_argument("url")
    dc.add_argument("--pattern")
    im = sub.add_parser("import-manifest", help="импорт задач из PDF по манифесту")
    im.add_argument("manifest")
    im.add_argument("--dry-run", action="store_true")
    im.add_argument("--parallel", type=int, default=4, help="сколько файлов обрабатывать одновременно")
    ve = sub.add_parser("verify-eval", help="калибровка проверки ответов на задачах с ключом")
    ve.add_argument("--sample", type=int, default=20)
    ve.add_argument("--seed", type=int, default=1)
    ve.add_argument("--subject", choices=["math", "physics"])
    ve.add_argument("--risky", action="store_true", help="только перебор, графики, графы")
    ve.add_argument("--no-escalate", action="store_true", help="не звать модель сильнее")
    ve.add_argument("--parallel", type=int, default=3)
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "preview":
        return cmd_preview(args)
    if args.cmd == "discover":
        return cmd_discover(args)
    if args.cmd == "import-manifest":
        return asyncio.run(cmd_import_manifest(args))
    if args.cmd == "verify-eval":
        return asyncio.run(cmd_verify_eval(args))
    fn = {"templates": cmd_templates, "hints": cmd_hints, "crosscheck": cmd_crosscheck}[args.cmd]
    return asyncio.run(fn(args))


if __name__ == "__main__":
    sys.exit(main())
