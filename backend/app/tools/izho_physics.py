"""Импорт теоретического тура IZhO по физике: условия + официальные решения (izho.kz), с рисунками.

Для каждого года модель получает два PDF — условия и официальные решения — и возвращает задачи по пунктам:
вопрос пункта, официальный ответ (число с единицами или формула), где на странице рисунок.
Рисунки вырезаются из PDF условий в картинки (data/figures). Затем официальный ответ перепроверяется:
Haiku решает пункт сам, не видя ответа; при расхождении — Sonnet. Если и Sonnet не согласен с официальным
ответом, пункт не берётся (возможна ошибка в источнике) — такие случаи печатаются в отчёте.

Запуск из папки backend:
    python -m app.tools.izho_physics --years 2012 2013 --budget 0.5
    python -m app.tools.izho_physics --all --budget 3
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import formula
from ..bank import Problem, closed_reason, figures_dir, load_bank, problems_dir
from ..checker import format_number
from ..importer import fetch_pdf
from ..llm import _record_usage, usage_cost
from ..units import UnitError, parse_unit

OLYMPIAD = "Международная Жаутыковская олимпиада (IZhO)"
B = "https://izho.kz/wp-content/uploads/"
# год → (условия, официальные решения)
PAIRS = {
    2010: ("2018/12/IZhO-2010-Theory_rus_f.pdf", "2018/12/IZhO-2010-Theory_rus_sol_f.pdf"),
    2011: ("2018/12/IZhO-2011-Theory_rus_f.pdf", "2018/12/IZhO-2011-Theory_rus_sol_f.pdf"),
    2012: ("2018/12/IZhO-2012-Theory_rus_final.pdf", "2018/12/IZhO-2012-Theory_rus_sol_final.pdf"),
    2013: ("2018/12/IZhO-2013-Theory_rus_final.pdf", "2018/12/IZhO-2013-Theory_rus_sol_final.pdf"),
    2014: ("2018/12/izho14rus1.pdf", "2018/12/izho14rus1sol.pdf"),
    2016: ("2018/01/IZhO-2016-Theory_rus.pdf", "2018/01/IZhO-2016-Theory_rus_sol.pdf"),
    2017: ("2018/01/IZhO-2017-Theory_rus.pdf", "2018/01/IZhO-2017-Theory_rus_sol-ilovepdf-compressed.pdf"),
    2018: ("2018/01/IZhO-2018-Theory_rus.pdf", "2018/01/IZhO-2018-Theory_rus_sol.pdf"),
    2019: ("2019/01/IZhO-2019-Theory_rus.pdf", "2019/01/IZhO-2019-Theory_rus_sol.pdf"),
    2020: ("2020/01/IZhO-2020-Theory_rus.pdf", "2020/01/IZhO-2020-Theory_eng_sol.pdf"),
    2023: ("2023/02/IZhO-2023-PhysTheory_2023.pdf", "2023/02/IZhO-2023-PhysTheory_sol_2023.pdf"),
    2024: ("2024/12/IZhO-2024-PhysTheory_2024.pdf", "2024/12/IZhO-2024-PhysTheory_sol.pdf"),
}
HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
NUM_TOL = 0.02  # перепроверка числа: 2% (официальные ответы округлены)

EXTRACT_SYSTEM = """Ты аккуратно переносишь олимпиадные задачи по физике из официальных PDF в базу данных.
Ничего не придумывай: условие — только из файла условий, ответ — только из файла официальных решений.
Отвечай только JSON."""

EXTRACT_PROMPT = """Первый PDF — условия {title} {year} года,
второй — официальные решения. Выдели ВСЕ задачи и их пункты (вопросы).

Для каждой задачи:
- "number": номер задачи (целое);
- "title": короткое название по-русски (2–4 слова); "topic": тема по-русски (1–2 слова);
- "intro": общее условие задачи дословно на русском (без вопросов пунктов), формулы в LaTeX внутри $...$;
- "figures": рисунки ИЗ ФАЙЛА УСЛОВИЙ, нужные для понимания задачи: список
  {{"page": номер страницы в PDF условий (с 1), "box": [x0, y0, x1, y1]}} — границы рисунка в долях
  ширины и высоты страницы (0..1, от левого верхнего угла), с небольшим запасом, вместе с подписями на рисунке;
- "parts": список пунктов, у каждого:
  - "label": номер пункта как в документе ("1", "2.3", "A1");
  - "question": вопрос пункта так, чтобы его можно было решать отдельно (нужные данные и результаты
    предыдущих пунктов впиши как известные);
  - "kind": "number" — ответ число; "formula" — ответ выражение через буквы условия;
    "other" — доказательство, график, качественный ответ, несколько ответов;
  - "value", "unit": для "number" — число из официального решения и единицы ("м/с", "Дж"), без единиц — null;
  - "formula": для "formula" — официальный ответ в записи Python: 17*g/29, 2*pi*sqrt(l/g), v0**2*sin(2*alpha)/g;
    только обозначения из "variables", константы — числами или pi;
  - "variables": для "formula" — словарь обозначений {{"g": "ускорение свободного падения", ...}}:
    имена латиницей и цифрами (v0, m1, alpha, theta), только величины, заданные в условии;
  - "solution": кратко — как получен ответ в официальном решении (2–5 строк, формулы в $...$).
Если ответа на пункт в официальном решении нет — "kind": "other".

Верни JSON: {{"problems": [...]}}"""

SOLVE_SYSTEM = """Ты сильный олимпиадник по физике. Решай внимательно и честно. Отвечай только JSON."""

SOLVE_PROMPT = """Задача (рисунки к ней приложены, если есть):
{intro}

Реши каждый вопрос (Q1, Q2, …) и дай итоговый ответ в указанном виде.
{parts}

Ответ на вопрос «число» — {{"id": "Q1", "value": число}} строго в указанных единицах.
Ответ на вопрос «формула» — {{"id": "Q2", "formula": "запись Python"}} только через указанные обозначения
(sqrt, sin, cos, tan, exp, log, pi разрешены).
Если не уверен — всё равно дай свой лучший ответ.
Верни JSON: {{"answers": [...]}}"""


@dataclass
class Report:
    added: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, why: str) -> None:
        self.skipped[why] = self.skipped.get(why, 0) + 1


def _client():
    """Отдельный клиент: решение трудной задачи с размышлениями идёт дольше, чем 90 с из настроек чата."""
    import os

    import anthropic

    return anthropic.AsyncAnthropic(
        api_key=os.environ.get("OLYMP_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("OLYMP_ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        timeout=600,
        max_retries=2,
    )


async def _ask(client, model: str, system: str, content: list[dict], max_tokens: int = 32000) -> dict:
    msg = await client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": content}]
    )
    _record_usage(model, msg.usage)
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("в ответе модели нет JSON")
    return json.loads(m.group(0), strict=False)


def _pdf_block(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}


def _image_block(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def crop_figure(pdf: Path, page: int, box: list[float], name: str) -> str | None:
    """Вырезать рисунок со страницы PDF в data/figures/<name>.png. None — если границы негодные."""
    import pypdfium2 as pdfium

    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    pad = 0.005  # небольшой запас: при большем в картинку попадают обрывки соседнего текста
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(1, x1 + pad), min(1, y1 + pad)
    if x1 - x0 < 0.05 or y1 - y0 < 0.03:
        return None
    doc = pdfium.PdfDocument(str(pdf))
    if not 1 <= page <= len(doc):
        return None
    img = doc[page - 1].render(scale=2.5).to_pil()
    w, h = img.size
    crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))).convert("L")
    if crop.width > 1400:
        crop = crop.resize((1400, int(crop.height * 1400 / crop.width)))
    out = figures_dir() / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    crop.save(buf, format="PNG", optimize=True)
    out.write_bytes(buf.getvalue())
    return out.name


def _matches(part: dict, got: dict | None) -> bool:
    """Совпадает ли ответ модели с официальным (число с учётом единиц — 2%, формула — равносильность)."""
    if not got:
        return False
    try:
        if part["kind"] == "formula":
            names = list(part["variables"])
            mine = formula.parse(str(got.get("formula", "")), names)
            return formula.equivalent(mine, formula.parse(part["formula"], names), names)
        # Модель отвечает числом в тех же единицах, что и официальный ответ.
        got_v, want = float(got.get("value")), float(part["value"])
        return abs(got_v - want) <= max(NUM_TOL * abs(want), 1e-9)
    except (formula.FormulaError, TypeError, ValueError, UnitError):
        return False


def _ask_line(i: int, p: dict) -> str:
    if p["kind"] == "formula":
        names = ", ".join(f"{k} — {v}" for k, v in p["variables"].items())
        return f"Q{i}. {p['question']}\n   Ответ — формула через обозначения: {names}."
    unit = p.get("unit")
    return f"Q{i}. {p['question']}\n   Ответ — число" + (
        f" в единицах «{unit}»." if unit else " (безразмерное)."
    )


async def _solve(
    client, model: str, intro: str, figs: list[Path], parts: list[dict], cache: Path
) -> list[dict | None]:
    """Ответы модели на пункты (в том же порядке). Ответы кэшируются: повторный запуск не платит."""
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        listing = "\n".join(_ask_line(i, p) for i, p in enumerate(parts, 1))
        prompt = SOLVE_PROMPT.format(intro=intro, parts=listing)
        content = [*(_image_block(f) for f in figs), {"type": "text", "text": prompt}]
        data = await _ask(client, model, SOLVE_SYSTEM, content, max_tokens=24000)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    by_id = {str(a.get("id", "")).upper(): a for a in data.get("answers", []) if isinstance(a, dict)}
    return [by_id.get(f"Q{i}") for i in range(1, len(parts) + 1)]


def _clean_part(p: dict) -> dict | None:
    """Проверить и нормализовать пункт: годный числовой или формульный ответ. None — пункт не берём."""
    kind = p.get("kind")
    if kind == "number":
        try:
            p["value"] = float(p["value"])
        except (TypeError, ValueError, KeyError):
            return None
        unit = (p.get("unit") or "").replace("^3", "³").replace("^2", "²").strip() or None
        if unit:
            try:
                parse_unit(unit)
            except UnitError:
                return None
        p["unit"] = unit
        return p
    if kind == "formula":
        variables = {str(k): str(v) for k, v in (p.get("variables") or {}).items()}
        if not variables or not all(formula.NAME_RE.match(k) for k in variables):
            return None
        try:
            formula.parse(str(p.get("formula", "")), list(variables))
        except formula.FormulaError:
            return None
        p["variables"] = variables
        return p
    return None


def _write(problem: Problem) -> None:
    data = problem.model_dump(mode="json", exclude_none=True)
    path = problems_dir() / f"{problem.id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def import_year(client, year: int, budget: float, dry_run: bool) -> Report:
    return await import_pair(
        client,
        olympiad=OLYMPIAD,
        slug="izho",
        stage="international",
        year=year,
        grade=None,
        tasks_url=B + PAIRS[year][0],
        sol_url=B + PAIRS[year][1],
        title="теоретического тура Международной Жаутыковской олимпиады",
        budget=budget,
        dry_run=dry_run,
    )


async def import_pair(
    client,
    *,
    olympiad: str,
    slug: str,
    stage: str,
    year: int,
    grade: int | None,
    tasks_url: str,
    sol_url: str,
    title: str,
    budget: float,
    dry_run: bool,
    cache_name: str = "izho-phys",
    replace_old: bool = True,
    tag: str = "",
) -> Report:
    """Физика из пары PDF (условия + официальные решения): рисунки вырезаются, ответ перепроверяется моделями."""
    rep = Report()
    tasks_pdf, sol_pdf = fetch_pdf(tasks_url), fetch_pdf(sol_url)
    key = f"{slug}-{year}-{grade or 0}{tag}"
    prefix = f"{slug}-{year}-phys{grade or ''}{tag}"
    cache_dir = Path(figures_dir()).parent / "raw" / cache_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    extract_cache = cache_dir / f"{key}-extract.json"
    if extract_cache.exists():
        data = json.loads(extract_cache.read_text(encoding="utf-8"))
    else:
        prompt = EXTRACT_PROMPT.format(title=title, year=year)
        content = [_pdf_block(tasks_pdf), _pdf_block(sol_pdf), {"type": "text", "text": prompt}]
        data = await _ask(client, HAIKU, EXTRACT_SYSTEM, content)
        extract_cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    bank = load_bank()
    for prob in data.get("problems", []):
        n = int(prob.get("number") or 0)
        intro = str(prob.get("intro") or "").strip()
        if not n or len(intro) < 40:
            rep.skip("нет условия")
            continue
        parts = []
        for p in prob.get("parts", []):
            p = _clean_part(dict(p)) if str(p.get("question") or "").strip() else None
            if p:
                parts.append(p)
            else:
                rep.skip("пункт без числа/формулы")
        if not parts:
            continue
        if not replace_old and any(
            q.source.olympiad == olympiad
            and q.subject == "physics"
            and (q.source.year, q.source.stage, q.source.grade, q.source.number) == (year, stage, grade, n)
            for q in bank.values()
        ):
            rep.skip("уже в банке")  # не тратим деньги на перепроверку того, что уже есть
            continue
        figs: list[str] = []
        for k, f in enumerate(prob.get("figures") or [], 1):
            page, box = int(f.get("page") or 0), f.get("box") or []
            name = crop_figure(tasks_pdf, page, box, f"{prefix}-{n}-fig{k}")
            if name:
                figs.append(name)
        fig_paths = [figures_dir() / f for f in figs]
        # Перепроверка: Haiku решает сам; расхождения — Sonnet; не сошлось и у Sonnet — пункт не берём.
        if usage_cost() >= budget:
            rep.skip("бюджет исчерпан")
            continue
        try:
            haiku = await _solve(client, HAIKU, intro, fig_paths, parts, cache_dir / f"{key}-{n}-haiku.json")
        except ValueError:
            haiku = [None] * len(parts)
        doubtful = [p for p, a in zip(parts, haiku) if not _matches(p, a)]
        if doubtful and usage_cost() >= budget:
            rep.skip("бюджет исчерпан до проверки Sonnet")
            continue  # не бракуем — просто не проверили; повторный запуск продолжит
        sonnet: list[dict | None] = []
        if doubtful:
            try:
                sonnet = await _solve(
                    client, SONNET, intro, fig_paths, doubtful, cache_dir / f"{key}-{n}-sonnet.json"
                )
            except ValueError:
                sonnet = [None] * len(doubtful)
        bad = {str(p["label"]) for p, a in zip(doubtful, sonnet) if not _matches(p, a)}
        # Старые пункты этой задачи (без рисунков) заменяем новыми — без повторов.
        old = [
            pid
            for pid, q in bank.items()
            if q.source.olympiad == olympiad
            and q.subject == "physics"
            and q.source.year == year
            and q.source.stage == stage
            and q.source.grade == grade
            and q.source.number == n
        ]
        if old and not replace_old:
            rep.skip("уже в банке")
            continue
        if not dry_run:
            for pid in old:
                (problems_dir() / f"{pid}.json").unlink(missing_ok=True)
        for p in parts:
            label = str(p["label"])
            pid = f"{prefix}-{n}-p{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-') or 'x'}"
            if label in bad:
                shown = p.get("formula") or f"{format_number(p['value'])} {p.get('unit') or ''}"
                rep.dropped.append(f"{pid}: официальный ответ {shown} — не подтвердили ни Haiku, ни Sonnet")
                continue
            if p["kind"] == "formula":
                answer = {"formula": p["formula"], "variables": p["variables"]}
            else:
                answer = {"value": p["value"], **({"unit": p["unit"]} if p["unit"] else {})}
            raw = {
                "id": pid,
                "subject": "physics",
                "topic": str(prob.get("topic") or "Разное")[:40],
                "title": f"{str(prob.get('title') or f'Задача {n}')[:50]}, пункт {label}",
                "statement": f"{intro}\n\n**Пункт {label}.** {str(p['question']).strip()}",
                "answer": answer,
                "source": {
                    "olympiad": olympiad,
                    "year": year,
                    "stage": stage,
                    **({"grade": grade} if grade else {}),
                    "number": n,
                    "url": sol_url,
                },
                "solution": str(p.get("solution") or "").strip() or None,
                "figures": figs,
            }
            try:
                problem = Problem.model_validate(raw)
            except ValueError as exc:
                rep.skip(f"формат: {str(exc).splitlines()[-1][:50]}")
                continue
            if not dry_run:
                _write(problem)
            rep.added.append(pid)
    return rep


async def main_async(args) -> int:
    if closed_reason(OLYMPIAD):
        print("Олимпиада закрыта для Казахстана", file=sys.stderr)
        return 2
    years = sorted(PAIRS) if args.all else args.years
    client = _client()
    total_added = 0
    try:
        for y in years:
            if usage_cost() >= args.budget:
                print(f"{y}: пропущен — бюджет исчерпан")
                continue
            try:
                rep = await import_year(client, y, args.budget, args.dry_run)
            except Exception as exc:  # один год не должен ронять весь импорт
                print(f"{y}: ошибка — {type(exc).__name__}: {str(exc)[:200]}")
                continue
            total_added += len(rep.added)
            print(
                f"{y}: добавлено {len(rep.added)}, не подтверждено {len(rep.dropped)}, пропущено {rep.skipped}"
            )
            for d in rep.dropped:
                print("   ", d)
    finally:
        await client.close()
    print(f"\nВсего добавлено: {total_added}\nРасход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="izho_physics")
    ap.add_argument("--years", type=int, nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    ap.add_argument("--dry-run", action="store_true")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
