"""Сборники задач по физике из СКАНОВ книг (fizmat.space): условия и ответы читает Haiku по картинкам страниц.

Книга — PDF без текстового слоя. Страницы режутся на окна по 6 штук (последняя страница окна повторяется в
следующем, чтобы условие или решение не обрывалось на границе). Для каждого окна Haiku возвращает задачи (условие,
номер, границы рисунков) и ответы (из раздела ответов книги). Задача берётся, только если в книге есть и условие, и
ОДИН ответ — число с единицами или формула — под тем же номером. Дальше ответ перепроверяется как у IZhO
(app/tools/izho_physics.py): Haiku решает сам, не видя ответа; при расхождении — Sonnet; не сошлось — задача не берётся.
Всё кэшируется в data/raw/scan: повторный запуск не платит за уже сделанное.

Запуск из папки backend:
    python -m app.tools.scan_book zam7 --pages 8-19,301-306 --budget 0.5     # проба на нескольких страницах
    python -m app.tools.scan_book gelfgat --budget 3
    python -m app.tools.scan_book gelfgat --extract-only                      # только прочитать страницы
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..bank import Problem, closed_reason, figures_dir, is_trusted_url, load_bank, save_problem
from ..importer import raw_dir
from ..llm import _record_usage, usage_cost
from .izho_physics import (
    HAIKU,
    SONNET,
    _ask,
    _clean_part,
    _client,
    _image_block,
    _matches,
    _solve,
    crop_figure,
)

CHUNK = 6  # страниц в одном запросе
BOOK_TOL = 0.20  # постоянные в разных справочниках расходятся заметно: плотность 1200 и 1400 — это 15%
STUDENT_TOL = 0.05  # меньше нельзя: книга округляет до двух значащих цифр
SCALE = 1.7  # масштаб отрисовки страницы: мельче — модель путает цифры

EXTRACT_SYSTEM = """Ты аккуратно переносишь задачи по физике из сканов школьных сборников в базу данных.
Ничего не придумывай и не решай: условие — только из раздела задач, ответ — только из раздела ответов книги.
Отвечай только JSON."""

EXTRACT_PROMPT = """Перед тобой страницы сборника «{title}». Над каждой картинкой написан номер страницы файла.
Верни все ЗАДАЧИ и все ОТВЕТЫ, которые видны на этих страницах:

{{"items": [
  {{"kind": "problem", "label": "1.25", "text": "...", "title": "...", "topic": "...", "stars": 0,
    "figures": [{{"page": 12, "box": [0.1, 0.4, 0.5, 0.6]}}], "complete": true}},
  {{"kind": "answer", "label": "1.25", "answer_kind": "number", "value": 200, "unit": "м", "formula": null,
    "variables": {{}}, "solution": "...", "complete": true}}
]}}

Правила для задач:
- "label" — номер задачи как напечатан ("1.25", "3.80", "Р.16.2"); тесты с вариантами А–Д, теорию, таблицы и
  примеры решений пропускай;
- "text" — условие дословно на русском, формулы в LaTeX внутри $...$, без ответа и без подсказок;
- "title" — название из 2–4 слов; "topic" — раздел физики по заголовку главы (1–2 слова);
- "stars" — число звёздочек после номера (0, если нет);
- "figures" — рисунки к этой задаче: {{"page": номер страницы файла, "box": [x0, y0, x1, y1]}} в долях ширины и
  высоты страницы (0..1, от левого верхнего угла), вместе с подписью «Рис. …»; нет рисунка — [];
- "complete": false, если условие обрывается на краю последней страницы.
Правила для ответов (раздел «Ответы» или «Ответы, указания, решения»):
- "label" — номер задачи, к которой относится ответ;
- "answer_kind": "number" — один числовой ответ; "formula" — один ответ-выражение через буквы условия;
  "other" — несколько ответов, пункты а) и б), график, рисунок, качественный ответ, доказательство;
- для "number": "value" — число (как в книге, не округляй) и "unit" ("м/с", "кДж", "г/см³"), без единиц — null;
- для "formula": "formula" — запись Python: m*g/3, 2*pi*sqrt(l/g); "variables" — {{"m": "масса", ...}} латиницей и
  цифрами только величины из условия; числовые константы не вноси;
- "solution" — как получен ответ, кратко: 2–5 строк, формулы в $...$ (если решения нет, пустая строка);
- "complete": false, если ответ или решение обрываются на краю последней страницы.
Поля со значением null, пустой строкой, пустым списком или словарём не пиши — ответ должен быть коротким.
Если на страницах нет ни задач, ни ответов, верни {{"items": []}}."""


OTHERS_PROMPT = """Перед тобой страницы с ответами сборника «{title}». Над каждой картинкой написан номер страницы файла.
Нужны ответы только к задачам с номерами: {labels}. Остальные пропускай.

Верни {{"answers": [{{"label": "1.25", "solution": "...", "parts": [
  {{"part": "а", "kind": "number", "value": 48, "unit": "км/ч"}},
  {{"part": "б", "kind": "formula", "formula": "m*g/3", "variables": {{"m": "масса"}}}},
  {{"part": "в", "kind": "text", "text": "не изменится"}}
]}}]}}

Правила:
- каждый пункт ответа (а, б, 1, 2) — отдельная запись в "parts"; несколько величин без пунктов — тоже отдельные
  записи, тогда "part" — обозначение величины ("T1", "T2");
- "number": значение как в книге, не округляй, и единицы; без единиц "unit" не пиши;
- "formula": запись Python только через величины из условия, "variables" латиницей;
- "text": качественный ответ дословно. Если ответ — график или рисунок, опиши его словами точно: что по осям,
  форма линии, значения в характерных точках;
- "solution": ход решения кратко, 2–5 строк, формулы в $...$; если решения в книге нет, поле не пиши.
Числа и слова бери только из книги, ничего не придумывай. Отвечай только JSON."""

TABLES_PROMPT = """Перепиши текстом все справочные таблицы и значения постоянных с этих страниц книги:
вещество или величина, значение, единицы. Числа только со страниц, ничего не добавляй и не округляй. Только текст."""

TABLES_NOTE = """Справочные данные из этой книги. Если величины нет в условии, бери её отсюда, других значений не используй:
{tables}

Задача:
{statement}"""

JUDGE_PROMPT = """Условие задачи (рисунки приложены, если есть):
{statement}

Ответ из сборника: {answer}

Реши задачу сам и сравни со смыслом ответа из сборника. Если ответ верен, верни {{"agree": true}}, иначе {{"agree": false}}."""


@dataclass(frozen=True)
class Book:
    slug: str
    title: str
    url: str
    grade: int | None
    tables: tuple[int, ...]  # страницы со справочными таблицами книги


BOOKS = {
    "zam7": Book(
        "zam7",
        "Замятнин М. Ю. (ред.). Сборник задач по физике",
        "https://fizmat.space/library/files/%D0%97%D0%B0%D0%BC%D1%8F%D1%82%D0%BD%D0%B8%D0%BD_7_"
        "%D0%BA%D0%BB%D0%B0%D1%81%D1%81.pdf",
        7,
        (342, 343),
    ),
    "gelfgat": Book(
        "gelfgat",
        "Гельфгат И. М., Генденштейн Л. Э., Кирик Л. А. 1001 задача по физике",
        "https://fizmat.space/library/files/Gelfgat1001.pdf",
        None,
        (589, 590, 591, 593),
    ),
}
LABEL_ASCII = {"Р": "r", "Ф": "f", "Т": "t", "М": "m", "А": "a", "Б": "b", "В": "v"}


def fetch_book(book: Book) -> Path:
    """Скачать PDF книги (только с проверенного сайта) в data/raw; повторно не качает."""
    if not is_trusted_url(book.url):
        raise SystemExit(f"{book.url}: сайт не из data/sources.json")
    path = raw_dir() / (hashlib.sha1(book.url.encode()).hexdigest()[:16] + ".pdf")
    if not path.exists():
        part = path.with_suffix(".part")
        with httpx.stream("GET", book.url, timeout=300, follow_redirects=True) as r:
            r.raise_for_status()
            with part.open("wb") as f:
                for block in r.iter_bytes():
                    f.write(block)
        part.rename(path)
    with path.open("rb") as f:
        if f.read(4) != b"%PDF":
            raise SystemExit(f"{book.url}: это не PDF")
    return path


def parse_pages(spec: str | None, total: int) -> list[int]:
    """«8-19,301-306» → номера страниц с 1; без аргумента — вся книга."""
    if not spec:
        return list(range(1, total + 1))
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        out += range(int(a), int(b or a) + 1)
    return sorted({p for p in out if 1 <= p <= total})


def windows(pages: list[int]) -> list[list[int]]:
    """Окна по CHUNK страниц внутри непрерывных кусков; соседние окна делят одну страницу."""
    out: list[list[int]] = []
    i = 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1 and j - i + 1 < CHUNK:
            j += 1
        out.append(pages[i : j + 1])
        more = j + 1 < len(pages) and pages[j + 1] == pages[j] + 1
        i = j if more and j > i else j + 1
    return out


def label_key(label: object) -> str:
    """«1,25.» → «1.25»: ключ для сопоставления условия и ответа."""
    return re.sub(r"\s+", "", str(label or "")).replace(",", ".").strip(".")


def slug_of(label: str) -> str:
    s = "".join(LABEL_ASCII.get(ch, ch) for ch in label).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def merge(windows_data: list[tuple[list[int], dict]]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Условия и ответы по номеру. Повторы (страница-нахлёст) — берём полную и более длинную запись."""
    problems: dict[str, dict] = {}
    answers: dict[str, dict] = {}
    for pages, data in windows_data:
        for it in data.get("items") or []:
            if not isinstance(it, dict) or it.get("kind") not in ("problem", "answer"):
                continue
            key = label_key(it.get("label"))
            if not key:
                continue
            store = problems if it["kind"] == "problem" else answers
            size = len(str(it.get("text" if it["kind"] == "problem" else "solution") or ""))
            old = store.get(key)
            if old is None or (bool(it.get("complete", True)), size) > (
                bool(old.get("complete", True)),
                old["_size"],
            ):
                store[key] = {**it, "_size": size, "_page": pages[0]}
    return problems, answers


def candidates(book: Book, problems: dict[str, dict], answers: dict[str, dict]) -> list[dict]:
    """Задачи, у которых в книге есть условие и один числовой или формульный ответ."""
    out = []
    for key, pr in problems.items():
        ans = answers.get(key)
        text = str(pr.get("text") or "").strip()
        if not ans or len(text) < 25 or pr.get("complete") is False or ans.get("complete") is False:
            continue
        if ans.get("answer_kind") not in ("number", "formula"):
            continue
        part = _clean_part(
            {
                "label": key,
                "kind": ans["answer_kind"],
                "value": ans.get("value"),
                "unit": ans.get("unit"),
                "formula": ans.get("formula"),
                "variables": ans.get("variables"),
                "question": "Дай ответ на вопрос задачи.",
                "solution": ans.get("solution"),
            }
        )
        if part:
            out.append(
                {
                    "key": key,
                    "shown": key,
                    "pid": f"{book.slug}-{slug_of(key)}",
                    "problem": pr,
                    "statement": text,
                    "solution": ans.get("solution"),
                    "part": part,
                }
            )
    out.sort(key=lambda c: -int(c["problem"].get("stars") or 0))
    return out


def part_candidates(book: Book, problems: dict[str, dict], others: dict[str, dict]) -> list[dict]:
    """Ответы из нескольких частей, графики и качественные ответы: каждая часть — отдельная задача."""
    out = []
    for key, ans in others.items():
        pr = problems.get(key) or {}
        text = str(pr.get("text") or "").strip()
        parts = [p for p in ans.get("parts") or [] if isinstance(p, dict)]
        if len(text) < 25 or pr.get("complete") is False:
            continue
        book_solution = str(ans.get("solution") or "").strip()
        for i, p in enumerate(parts, 1):
            name = str(p.get("part") or i).strip().rstrip(")") if len(parts) > 1 else ""
            statement = f"{text}\n\n**Часть {name}.** Ответь только на эту часть задачи." if name else text
            common = {
                "key": key,
                "shown": f"{key}, {name}" if name else key,
                "pid": f"{book.slug}-{slug_of(key)}" + (f"-p{i}" if name else ""),
                "problem": pr,
                "statement": statement,
            }
            if p.get("kind") == "text":
                said = str(p.get("text") or "").strip()
                if said:
                    solution = f"Ответ из книги: {said}" + (f"\n\n{book_solution}" if book_solution else "")
                    out.append({**common, "solution": solution, "part": {"kind": "text", "text": said}})
                continue
            part = _clean_part(
                {
                    "label": key,
                    "kind": p.get("kind"),
                    "value": p.get("value"),
                    "unit": p.get("unit"),
                    "formula": p.get("formula"),
                    "variables": p.get("variables"),
                    "question": "Дай ответ на вопрос задачи.",
                }
            )
            if part:
                out.append({**common, "solution": book_solution, "part": part})
    return out


def page_block(doc, page: int) -> dict:
    im = doc[page - 1].render(scale=SCALE).to_pil().convert("L")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=72)
    data = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def parse_items(text: str) -> dict:
    """JSON ответа модели. Если вывод оборвался (лимит токенов) — берём целые записи до обрыва."""
    m = re.search(r"\{.*", text, re.S)
    if not m:
        raise ValueError("в ответе модели нет JSON")
    raw = m.group(0)
    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError as exc:
        # Одна испорченная запись не должна стоить всего окна: разбираем записи по отдельности.
        dec = json.JSONDecoder(strict=False)
        for start, key in ((r'\{\s*"kind"', "items"), (r'\{\s*"label"', "answers")):
            records = []
            for found in re.finditer(start, raw):
                try:
                    records.append(dec.raw_decode(raw, found.start())[0])
                except json.JSONDecodeError:
                    continue
            if records:
                return {key: records}
        head = raw[: exc.pos]
        cut = head.rfind("},")
        if cut < 0:
            raise ValueError("JSON не разобрать") from exc
        for tail in ("]}", "]}]}"):  # обрыв внутри списка записей или внутри "parts" записи
            try:
                return json.loads(head[: cut + 1] + tail, strict=False)
            except json.JSONDecodeError:
                continue
        raise ValueError("JSON не разобрать") from exc


async def ask_items(client, content: list[dict]) -> dict:
    msg = await client.messages.create(
        model=HAIKU,
        max_tokens=32000,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    _record_usage(HAIKU, msg.usage)
    return parse_items("".join(b.text for b in msg.content if b.type == "text"))


async def extract_window(
    client, doc, book: Book, pages: list[int], budget: float, sem, prompt: str | None = None, tag: str = ""
) -> dict | None:
    cache_dir = raw_dir() / "scan"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{book.slug}{tag}-{pages[0]}-{pages[-1]}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    async with sem:
        if usage_cost() >= budget:
            return None
        content: list[dict] = []
        for p in pages:
            content += [{"type": "text", "text": f"Страница {p}:"}, page_block(doc, p)]
        content.append({"type": "text", "text": prompt or EXTRACT_PROMPT.format(title=book.title)})
        try:
            data = await ask_items(client, content)
        except Exception as exc:  # одно окно не должно ронять всю книгу
            print(f"страницы {pages[0]}–{pages[-1]}: ошибка — {type(exc).__name__}: {str(exc)[:120]}")
            return None
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def build_problem(book: Book, c: dict, figs: list[str]) -> Problem:
    pr, part = c["problem"], c["part"]
    if part["kind"] == "text":
        answer = {"proof": True}
    elif part["kind"] == "formula":
        answer = {"formula": part["formula"], "variables": part["variables"]}
    else:
        answer = {
            "value": part["value"],
            **({"unit": part["unit"]} if part["unit"] else {}),
            **({"rel_tol": c["rel_tol"]} if c.get("rel_tol") else {}),
        }
    title = f"{str(pr.get('title') or 'Задача')[:50]} ({c['shown']})"
    return Problem.model_validate(
        {
            "id": c["pid"],
            "subject": "physics",
            "topic": str(pr.get("topic") or "Разное")[:40],
            "title": title,
            "statement": c["statement"],
            "answer": answer,
            "source": {
                "olympiad": book.title,
                "stage": "collection",
                **({"grade": book.grade} if book.grade else {}),
                "url": f"{book.url}#page={pr['_page']}",
            },
            "solution": str(c.get("solution") or "").strip() or None,
            "figures": figs,
        }
    )


def accept(c: dict, got: dict | None) -> bool:
    """Совпал ли ответ модели с книгой. Запоминает допуск для ученика: не меньше найденного расхождения."""
    part = c["part"]
    if part["kind"] != "number":
        return _matches(part, got)
    try:
        mine, book = abs(float(got["value"])), abs(float(part["value"]))  # знак зависит от выбора оси
    except (TypeError, ValueError, KeyError):
        return False
    deviation = abs(mine - book) / max(book, 1e-12)
    if deviation > BOOK_TOL:
        return False
    c["rel_tol"] = min(BOOK_TOL, max(STUDENT_TOL, deviation * 1.2))
    return True


async def read_tables(client, doc, book: Book, budget: float) -> str:
    """Справочные таблицы книги текстом (один раз, дальше из кэша). Sonnet: здесь важна каждая цифра."""
    cache = raw_dir() / "scan" / f"{book.slug}-tables.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    content: list[dict] = [page_block(doc, p) for p in book.tables]
    content.append({"type": "text", "text": TABLES_PROMPT})
    msg = await client.messages.create(
        model=SONNET, max_tokens=8000, messages=[{"role": "user", "content": content}]
    )
    _record_usage(SONNET, msg.usage)
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    cache.write_text(text, encoding="utf-8")
    return text


async def retry_with_tables(client, todo: list[dict], tables: str, budget: float, cache_dir: Path) -> None:
    """Отсеянные числовые задачи решаем заново с постоянными из самой книги: Haiku, не сошлось — Sonnet."""
    sem = asyncio.Semaphore(4)

    async def one(c: dict) -> None:
        figs = [figures_dir() / f for f in c["figs"]]
        for model, name in ((HAIKU, "haiku"), (SONNET, "sonnet")):
            async with sem:
                if usage_cost() >= budget:
                    return
                try:
                    got = await _solve(
                        client,
                        model,
                        c["with_tables"],
                        figs,
                        [c["part"]],
                        cache_dir / f"{c['pid']}-tables-{name}.json",
                    )
                except Exception:
                    got = [None]
            if accept(c, got[0]):
                c["state"] = "ok"
                return

    bad = [c for c in todo if c["state"] == "bad" and c["part"]["kind"] == "number"]
    for c in bad:
        c["with_tables"] = TABLES_NOTE.format(tables=tables, statement=c["statement"])
    await asyncio.gather(*(one(c) for c in bad))


async def recheck(todo: list[dict], budget: float, cache_dir: Path) -> None:
    """Отсеянные числовые задачи без рисунка — через app/verify.py: модели разных производителей и программы.

    Задача возвращается, если проверка приняла ответ и он сошёлся с книгой (с учётом BOOK_TOL).
    """
    from ..verify import verify_answer

    sem = asyncio.Semaphore(2)  # у бесплатных моделей маленькие квоты

    async def one(c: dict) -> None:
        cache = cache_dir / f"{c['pid']}-verify.json"
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
        else:
            async with sem:
                if usage_cost() >= budget:
                    c["state"] = "pending"
                    return
                try:
                    v = await verify_answer(c.get("with_tables", c["statement"]), c["part"]["unit"])
                except Exception as exc:  # одна задача не должна ронять остальные; без кэша — повторим
                    print(f"{c['pid']}: проверка не удалась — {type(exc).__name__}")
                    return
            data = {"ok": v.accepted, "value": v.answer, "reason": v.reason}
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if data["ok"] and accept(c, data):
            c["state"] = "ok"

    await asyncio.gather(
        *(one(c) for c in todo if c["state"] == "bad" and c["part"]["kind"] == "number" and not c["figs"])
    )


async def judge(client, c: dict, cache: Path) -> bool:
    """Согласуется ли качественный ответ книги с задачей (Haiku решает сам и сравнивает)."""
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        prompt = JUDGE_PROMPT.format(statement=c["statement"], answer=c["part"]["text"])
        content = [*(_image_block(figures_dir() / f) for f in c["figs"]), {"type": "text", "text": prompt}]
        data = await _ask(
            client, HAIKU, "Ты сильный олимпиадник по физике. Отвечай только JSON.", content, 8000
        )
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data.get("agree") is True


async def read_others(
    client, doc, book: Book, done, problems, answers, budget: float, sem
) -> dict[str, dict]:
    """Перечитать страницы ответов для задач с ответом «other»: части, графики, качественные ответы."""
    wanted = {k for k, a in answers.items() if a.get("answer_kind") == "other" and k in problems}
    seen: set[str] = set()
    jobs = []
    for pages, data in done:
        here = {
            label_key(i.get("label"))
            for i in data.get("items") or []
            if isinstance(i, dict) and i.get("kind") == "answer"
        }
        labels = sorted((here & wanted) - seen)
        if labels:
            seen |= set(labels)
            prompt = OTHERS_PROMPT.format(title=book.title, labels=", ".join(labels))
            jobs.append(extract_window(client, doc, book, pages, budget, sem, prompt, "-others"))
    out: dict[str, dict] = {}
    for got in await asyncio.gather(*jobs):
        for a in (got or {}).get("answers") or []:
            if isinstance(a, dict) and label_key(a.get("label")) in wanted:
                out[label_key(a.get("label"))] = a
    return out


async def verify(
    client, book: Book, pdf: Path, cands: list[dict], budget: float, dry_run: bool, tables: str | None = None
):
    """Перепроверка и запись. Возвращает (сколько добавлено, список неподтверждённых)."""
    cache_dir = raw_dir() / "scan"
    bank = load_bank()
    sem = asyncio.Semaphore(4)
    todo = [c for c in cands if c["pid"] not in bank]

    async def haiku_pass(c: dict) -> None:
        figs: list[str] = []
        for k, f in enumerate(c["problem"].get("figures") or [], 1):
            try:
                name = crop_figure(pdf, int(f.get("page") or 0), f.get("box") or [], f"{c['pid']}-fig{k}")
            except (TypeError, ValueError):
                name = None
            if name:
                figs.append(name)
        c["figs"] = figs
        async with sem:
            if usage_cost() >= budget:
                c["state"] = "pending"
                return
            if c["part"]["kind"] == "text":  # сверить можно только по смыслу; нет согласия — не берём
                try:
                    agree = await judge(client, c, cache_dir / f"{c['pid']}-judge.json")
                except Exception:
                    agree = False
                c["state"] = "ok" if agree else "bad"
                return
            try:
                got = await _solve(
                    client,
                    HAIKU,
                    c["statement"],
                    [figures_dir() / f for f in figs],
                    [c["part"]],
                    cache_dir / f"{c['pid']}-haiku.json",
                )
            except Exception:
                got = [None]
        c["state"] = "ok" if accept(c, got[0]) else "doubt"

    await asyncio.gather(*(haiku_pass(c) for c in todo))
    for c in (c for c in todo if c["state"] == "doubt"):  # звёздочные первыми (см. candidates)
        if usage_cost() >= budget:
            c["state"] = "pending"
            continue
        try:
            got = await _solve(
                client,
                SONNET,
                c["statement"],
                [figures_dir() / f for f in c["figs"]],
                [c["part"]],
                cache_dir / f"{c['pid']}-sonnet.json",
            )
        except Exception:
            got = [None]
        c["state"] = "ok" if accept(c, got[0]) else "bad"
    if tables is not None:
        await retry_with_tables(client, todo, tables, budget, cache_dir)
        await recheck(todo, budget, cache_dir)
    added, dropped = 0, []
    for c in todo:
        if c["state"] == "ok":
            added += 1
            if not dry_run:
                save_problem(build_problem(book, c, c["figs"]))
            continue
        if c["state"] == "bad":
            dropped.append(f"{c['pid']}: ответ книги не подтвердили ни Haiku, ни Sonnet")
        if not dry_run:
            for f in c["figs"]:
                (figures_dir() / f).unlink(missing_ok=True)
    return added, dropped


async def main_async(args) -> int:
    import pypdfium2 as pdfium

    book = BOOKS[args.book]
    if closed_reason(book.title):
        print("Книга закрыта для Казахстана", file=sys.stderr)
        return 2
    pdf = fetch_book(book)
    doc = pdfium.PdfDocument(str(pdf))
    pages = parse_pages(args.pages, len(doc))
    client = _client()
    try:
        sem = asyncio.Semaphore(3)
        wins = windows(pages)
        results = await asyncio.gather(
            *(extract_window(client, doc, book, w, args.budget, sem) for w in wins)
        )
        done = [(w, d) for w, d in zip(wins, results, strict=True) if d is not None]
        problems, answers = merge(done)
        cands = candidates(book, problems, answers)
        others = await read_others(client, doc, book, done, problems, answers, args.budget, sem)
        cands += part_candidates(book, problems, others)
        print(
            f"окон: {len(done)}/{len(wins)}; задач в книге: {len(problems)}, ответов: {len(answers)}, "
            f"с одним числом или формулой: {len(cands)}"
        )
        if args.extract_only:
            print(f"Расход Claude: ${usage_cost():.4f}")
            return 0
        tables = await read_tables(client, doc, book, args.budget) if args.recheck else None
        added, dropped = await verify(client, book, pdf, cands, args.budget, args.dry_run, tables)
        pending = sum(1 for c in cands if c.get("state") == "pending")
        print(f"добавлено: {added}, не подтверждено: {len(dropped)}, ждёт бюджета: {pending}")
        for d in dropped[:30]:
            print("   ", d)
    finally:
        await client.close()
    print(f"Расход Claude: ${usage_cost():.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scan_book")
    ap.add_argument("book", choices=sorted(BOOKS))
    ap.add_argument("--pages", help="например 8-19,301-306 (с 1); по умолчанию вся книга")
    ap.add_argument("--budget", type=float, default=0.5, help="остановиться при таком расходе Claude, $")
    ap.add_argument(
        "--extract-only", action="store_true", help="только прочитать страницы, без проверки и записи"
    )
    ap.add_argument("--recheck", action="store_true", help="отсеянные прогнать через app/verify.py")
    ap.add_argument("--dry-run", action="store_true", help="не писать задачи в банк")
    return asyncio.run(main_async(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
