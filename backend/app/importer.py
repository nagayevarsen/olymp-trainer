"""Импорт задач из официальных PDF олимпиад.

Как это работает:
1. PDF скачивается ТОЛЬКО с сайта из data/sources.json (иначе ошибка).
2. Файл целиком отправляется в Gemini: модель выделяет задачи, ответы, класс,
   и отмечает, есть ли рисунок и задача ли это на доказательство.
3. В банк попадают только задачи с числовым ответом и без рисунка.
4. Защита от выдуманных ответов: число из ответа должно буквально встречаться
   в тексте официального PDF. Иначе задача отбрасывается.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from .bank import Problem, closed_reason, is_trusted_url, problems_dir
from .config import settings
from .llm import Image, LLMError, complete_json
from .units import UnitError, parse_unit

# У каждой модели своя бесплатная квота, поэтому параллельные запросы распределяются
# по моделям по кругу: если одна упёрлась в лимит, запрос уходит следующей.
IMPORT_MODELS = [
    "gemini:gemini-3-flash-preview",
    "gemini:gemini-3.5-flash-lite",
    "gemini:gemini-flash-lite-latest",
    "gemini:gemini-3.5-flash",
    "gemini:gemini-3.1-flash-lite",
]
_rr = 0


def _import_chain() -> list[str]:
    """Если задан IMPORT_MODEL (например anthropic:claude-haiku-5-5), он идёт первым,
    бесплатные Gemini остаются запасными."""
    global _rr
    _rr += 1
    k = _rr % len(IMPORT_MODELS)
    chain = IMPORT_MODELS[k:] + IMPORT_MODELS[:k]
    preferred = os.environ.get("IMPORT_MODEL")
    return [preferred, *chain] if preferred else chain


MAX_PDF_BYTES = 18 * 1024 * 1024
USER_AGENT = "OlympTrainer/0.1 (school olympiad training project; non-commercial)"


class ImportError_(RuntimeError):
    pass


def raw_dir() -> Path:
    d = Path(settings.data_dir) / "raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str) -> httpx.Response:
    if not is_trusted_url(url):
        raise ImportError_(f"{url} не из списка проверенных сайтов")
    for attempt in range(4):  # matol.ru иногда обрывает скачивание на середине файла
        try:
            resp = httpx.get(
                url,
                timeout=60,
                follow_redirects=True,
                verify=os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE") or True,
                headers={"User-Agent": USER_AGENT},
            )
            break
        except httpx.RemoteProtocolError:
            if attempt == 3:
                raise
    if not is_trusted_url(str(resp.url)):
        raise ImportError_(f"{url} перенаправил на непроверенный сайт {resp.url}")
    resp.raise_for_status()
    return resp


def discover(page_url: str, pattern: str | None = None) -> list[str]:
    """Найти ссылки на PDF на странице проверенного сайта."""
    html = _get(page_url).text
    links = []
    for href in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
        url = urljoin(page_url, unescape(href.strip()))
        if not re.search(r"\.pdf($|\?)", url, re.I):
            continue
        if pattern and not re.search(pattern, url, re.I):
            continue
        if is_trusted_url(url) and url not in links:
            links.append(url)
    return links


MAX_ZIP_BYTES = 80 * 1024 * 1024
ZIP_MEMBER = "#member="


def _fetch_zip(url: str) -> Path:
    path = raw_dir() / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".zip")
    if not path.exists():
        data = _get(url).content
        if not data.startswith(b"PK"):
            raise ImportError_(f"{url}: это не ZIP-архив")
        if len(data) > MAX_ZIP_BYTES:
            raise ImportError_(f"{url}: архив слишком большой ({len(data) // 1024 // 1024} МБ)")
        path.write_bytes(data)
    return path


def zip_members(url: str) -> list[str]:
    """PDF-файлы внутри ZIP-архива с проверенного сайта."""
    import zipfile

    with zipfile.ZipFile(_fetch_zip(url)) as z:
        return [i.filename for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(".pdf")]


def fetch_pdf(url: str) -> Path:
    """Скачать PDF. Адрес вида https://site/archive.zip#member=dir/file.pdf — PDF внутри архива:
    архив скачивается с проверенного сайта, файл читается из него в память (на диск ничего не
    распаковывается), размер проверяется до чтения."""
    path = raw_dir() / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".pdf")
    if not path.exists():
        if ZIP_MEMBER in url:
            import zipfile

            base, member = url.split(ZIP_MEMBER, 1)
            with zipfile.ZipFile(_fetch_zip(base)) as z:
                try:
                    info = z.getinfo(member)
                except KeyError as exc:
                    raise ImportError_(f"{url}: в архиве нет файла {member}") from exc
                if info.file_size > MAX_PDF_BYTES:
                    raise ImportError_(f"{url}: файл слишком большой ({info.file_size // 1024 // 1024} МБ)")
                data = z.read(info)
        else:
            data = _get(url).content
        if not data.startswith(b"%PDF"):
            raise ImportError_(f"{url}: это не PDF")
        if len(data) > MAX_PDF_BYTES:
            raise ImportError_(f"{url}: файл слишком большой ({len(data) // 1024 // 1024} МБ)")
        path.write_bytes(data)
    return path


def pdf_text(path: Path) -> str:
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, timeout=60
        )
        # Явно UTF-8: на Windows pdftotext и Python по умолчанию берут системную кодировку.
        return out.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return ""


EXTRACT_SYSTEM = """Ты аккуратно переносишь олимпиадные задачи из официальных PDF в базу данных.
Ничего не придумывай: условие и ответ берутся только из документа. Отвечай только JSON."""

EXTRACT_PROMPT = """Это официальный файл олимпиады: {olympiad}, {stage_name}, {year}.
Предмет: {subject_ru}.{grade_note}

Выдели ВСЕ задачи из файла. Для каждой верни объект:
- "number": номер задачи как в документе (строка, например "3" или "7.2");
- "grade": класс (число) или null, если не указан;
- "topic": тема по-русски одним-двумя словами (например "Кинематика", "Комбинаторика");
- "title": короткое название задачи по-русски (2–4 слова);
- "statement": полный текст условия на языке оригинала, дословно. Формулы и переменные в LaTeX
  внутри $...$ (например $v = 10$ м/с, $\\rho_в$). Без решения и без ответа;
- "has_figure": true, если для понимания условия нужен рисунок, график, таблица-картинка или схема;
- "kind": "numeric" — у задачи один итоговый числовой ответ; "proof" — доказательство;
  "multiple_choice" — выбор варианта; "other" — несколько ответов, формула, пример, да/нет и т.п.;
- "answer_value": итоговый числовой ответ из документа (число, десятичная точка), иначе null;
- "answer_unit": единицы ответа как в документе ("м/с", "г/см³", "%", "°", "кДж"), для чисел без единиц null;
- "answer_text": ответ дословно, как он написан в документе, иначе null.

Если в задаче несколько вопросов (пунктов) с разными ответами — kind = "multi" и добавь поле
"parts": список пунктов, у каждого:
  - "label": номер пункта как в документе ("1", "A.2", "б");
  - "question": вопрос этого пункта так, чтобы его можно было решать отдельно: если нужны данные
    или результаты предыдущих пунктов, впиши их в вопрос как известные;
  - "has_figure", "kind", "answer_value", "answer_unit", "answer_text" — как для задачи, но для этого пункта.
  Для "multi" поле "statement" — общее условие задачи без вопросов пунктов.
Если ответа в документе нет — answer_value = null.
Если одни и те же задачи даны в документе на двух языках (казахском и русском) — верни каждую
задачу один раз, в русской версии; казахскую используй только когда русской нет.

Верни JSON: {{"problems": [ ... ]}}"""

STAGE_RU = {
    "school": "школьный этап",
    "qualifying": "отборочный этап",
    "distance": "дистанционный этап",
    "district": "районный этап",
    "city": "городской этап",
    "region": "региональный этап",
    "republic": "республиканский этап",
    "final": "заключительный этап",
    "international": "международная олимпиада",
    "other": "",
}


@dataclass
class ImportReport:
    url: str
    found: int = 0
    added: list[str] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    model: str | None = None

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def _num_variants(x: float) -> list[str]:
    """Как число может быть записано в PDF: 26.3 → ["26.3", "26,3"], 0.4 → ["0,4", "0,40", ".4"]..."""
    out = set()
    for decimals in range(0, 5):
        s = f"{x:.{decimals}f}"
        if abs(float(s) - x) < 1e-9 * max(1, abs(x)):
            out.add(s)
            out.add(s.replace(".", ","))
            if decimals:
                for extra in range(1, 3):
                    t = s + "0" * extra
                    out.update({t, t.replace(".", ",")})
    if x == int(x):
        out.add(str(int(x)))
    return sorted(out, key=len)


def answer_in_text(value: float, text: str) -> bool:
    """Есть ли число в тексте PDF как отдельное число (не часть другого)."""
    flat = re.sub(r"\s+", " ", text)
    for v in _num_variants(value):
        if re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d])", flat):
            return True
    return False


MIN_PART_CONTEXT = 80
NO_QUESTION_RE = re.compile(
    r"не приведён|не приведен|не указан[оа]? в документе|в документе не|question (is )?not (given|stated)"
    r"|условие отсутствует|услови[ея] (задачи )?нет|приведено только решение|только решени[ея]",
    re.I,
)


PART_LABEL_RE = re.compile(r"\*\*Пункт[^*]*\*\*")


def expand_parts(items: list[dict]) -> list[dict]:
    """Задача из нескольких пунктов → отдельная задача на каждый пункт.

    Условие пункта = общее условие + вопрос пункта. Номер задачи сохраняется,
    пункт попадает в поле part (и в id задачи)."""
    out: list[dict] = []
    for it in items:
        parts = it.get("parts") if it.get("kind") == "multi" else None
        if not parts:
            out.append(it)
            continue
        base = (it.get("statement") or "").strip()
        for part in parts:
            if not isinstance(part, dict):
                continue
            label = str(part.get("label", "")).strip()
            question = (part.get("question") or "").strip()
            out.append(
                {
                    **it,
                    **{k: part.get(k) for k in ("answer_value", "answer_unit", "answer_text", "kind")},
                    "has_figure": bool(it.get("has_figure")) or bool(part.get("has_figure")),
                    "statement": f"{base}\n\n**Пункт {label}.** {question}"
                    if label
                    else f"{base}\n\n{question}",
                    "title": f"{(it.get('title') or 'Задача').strip()}, пункт {label}"[:60],
                    "part": label or str(len(out) + 1),
                    "base_len": len(base),
                    "parts": None,
                }
            )
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


async def import_pdf(
    url: str,
    *,
    olympiad: str,
    stage: str,
    year: int,
    subject: str,
    slug: str,
    grade: int | None = None,
    dry_run: bool = False,
    verify_missing: bool = False,
    budget: float | None = None,
) -> ImportReport:
    """verify_missing — если в файле нет ответа, получить его проверкой (app/verify.py):
    независимые решения разных моделей и программы; без согласия задача не берётся.
    budget — не начинать новую проверку, если расход Claude в процессе уже больше, $."""
    report = ImportReport(url=url)
    if reason := closed_reason(olympiad):
        report.error = f"олимпиада закрыта для Казахстана: {reason}"
        return report
    try:
        path = fetch_pdf(url)
    except (ImportError_, httpx.HTTPError) as exc:
        report.error = str(exc)
        return report
    text = pdf_text(path)

    prompt = EXTRACT_PROMPT.format(
        olympiad=olympiad,
        stage_name=STAGE_RU.get(stage, stage),
        year=year,
        subject_ru={"math": "математика", "physics": "физика"}[subject],
        grade_note=f" Класс: {grade}." if grade else "",
    )
    try:
        data, model = await complete_json(
            prompt,
            EXTRACT_SYSTEM,
            image=Image(path.read_bytes(), "application/pdf"),
            chain=_import_chain(),
        )
    except LLMError as exc:
        report.error = f"ИИ не смог разобрать файл: {exc}"
        return report

    report.model = model
    items = expand_parts(data.get("problems") or [])
    report.found = len(items)
    existing = {p.stem for p in problems_dir().glob("*.json")}
    for it in items:
        if it.get("has_figure"):
            report.skip("нужен рисунок")
            continue
        if it.get("kind") != "numeric":
            report.skip(f"не числовой ответ ({it.get('kind')})")
            continue
        value = it.get("answer_value")
        need_verify = not isinstance(value, (int, float))
        if need_verify and not verify_missing:
            report.skip("нет ответа в файле")
            continue
        if not need_verify and text and not answer_in_text(float(value), text):
            report.skip("ответ не найден в тексте PDF")
            continue
        unit = it.get("answer_unit") or None
        if unit:
            unit = unit.replace("^3", "³").replace("^2", "²").strip()
            try:
                parse_unit(unit)
            except UnitError:
                report.skip(f"непонятные единицы ({unit})")
                continue
        g = grade or it.get("grade")
        number = str(it.get("number", "")).strip()
        num_int = re.findall(r"\d+", number)
        pid = f"{slug}-{year}-{subject[:4]}{g or ''}-{_slug(number) or len(report.added) + 1}"
        if it.get("part"):
            pid += f"-p{_slug(it['part']) or 'x'}"
        if pid in existing:
            report.skip("уже в банке")
            continue
        raw = {
            "id": pid,
            "subject": subject,
            "topic": (it.get("topic") or "Разное").strip()[:40],
            "title": (it.get("title") or f"Задача {number}").strip()[:60],
            "statement": (it.get("statement") or "").strip(),
            "answer": {"value": float(value or 0), **({"unit": unit} if unit else {})},
            "source": {
                "olympiad": olympiad,
                "year": year,
                "stage": stage,
                **({"grade": int(g)} if isinstance(g, int) or (isinstance(g, str) and g.isdigit()) else {}),
                **({"number": int(num_int[-1])} if num_int else {}),
                "url": url,
            },
        }
        if len(raw["statement"]) < 40:
            report.skip("пустое условие")
            continue
        if it.get("part") and it.get("base_len", 0) < MIN_PART_CONTEXT:
            # Пункт без общего условия решать нельзя (например, в файле только решения).
            report.skip("у пункта нет общего условия")
            continue
        if NO_QUESTION_RE.search(raw["statement"]):
            report.skip("в файле нет текста вопроса")
            continue
        if subject == "physics" and not re.search(r"\d", PART_LABEL_RE.sub("", raw["statement"])):
            # Числовой ответ по физике без единого числа в условии — данные остались в таблице или рисунке.
            report.skip("в условии нет данных")
            continue
        if need_verify:
            from . import verify
            from .llm import usage_cost

            if budget is not None and usage_cost() >= budget:
                report.skip("бюджет исчерпан")
                continue
            v = await verify.verify_answer(raw["statement"], unit)
            if not v.accepted or v.answer is None:
                report.skip("проверка не подтвердила ответ")
                continue
            raw["answer"].update(value=float(v.answer), origin="verified", verified_by=v.verified_by)
        try:
            problem = Problem.model_validate(raw)
        except ValidationError as exc:
            report.skip(f"ошибка формата: {exc.errors()[0]['msg'][:60]}")
            continue
        if not dry_run:
            out = problems_dir() / f"{problem.id}.json"
            out.write_text(
                json.dumps(problem.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
        existing.add(problem.id)
        report.added.append(problem.id)
    return report
