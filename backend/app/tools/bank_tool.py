"""Утилита для работы с банком задач.

Запуск из папки backend:

    python -m app.tools.bank_tool check              # проверить все задачи и шаблоны
    python -m app.tools.bank_tool templates          # ИИ делает шаблоны для задач без шаблона
    python -m app.tools.bank_tool templates --id X   # ... только для задачи X (--force — пересоздать)
    python -m app.tools.bank_tool crosscheck         # другая модель решает варианты, сверяем ответы
    python -m app.tools.bank_tool hints              # ИИ пишет подсказки для задач без подсказок
    python -m app.tools.bank_tool preview X          # показать 3 варианта задачи X
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
    for p in _select(args.id):
        if p.template and not args.force:
            continue
        print(f"→ {p.id}: строю шаблон…")
        template, log = await ai.build_template(p)
        for line in log:
            print(f"     {line}")
        if template:
            p.template = template
            save_problem(p)
            print("     сохранено ✓")
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
    pv = sub.add_parser("preview")
    pv.add_argument("problem")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "preview":
        return cmd_preview(args)
    fn = {"templates": cmd_templates, "hints": cmd_hints, "crosscheck": cmd_crosscheck}[args.cmd]
    return asyncio.run(fn(args))


if __name__ == "__main__":
    sys.exit(main())
