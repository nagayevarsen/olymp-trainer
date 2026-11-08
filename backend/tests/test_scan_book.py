"""Сборники из сканов: окна страниц, сопоставление условия и ответа по номеру, отбор задач с одним ответом."""

from app.bank import STAGE_NAMES, load_bank
from app.contests import build_contests
from app.tools.scan_book import BOOKS, candidates, label_key, merge, parse_pages, slug_of, windows


def test_pages_and_windows_overlap_by_one_page():
    assert parse_pages("8-10,301", 400) == [8, 9, 10, 301]
    assert parse_pages(None, 3) == [1, 2, 3]
    assert parse_pages("2-99", 5) == [2, 3, 4, 5]
    # окна по 6 страниц делят последнюю страницу: условие не обрывается на границе
    assert windows(list(range(1, 14))) == [[1, 2, 3, 4, 5, 6], [6, 7, 8, 9, 10, 11], [11, 12, 13]]
    # разрыв между кусками — отдельное окно
    assert windows([1, 2, 10, 11]) == [[1, 2], [10, 11]]


def test_labels_become_ids():
    assert label_key(" 1,25. ") == "1.25"
    assert slug_of("1.25") == "1-25"
    assert slug_of("Р.16.2") == "r-16-2"


def _prob(label, text="Тело падает с высоты 20 м. Найдите время падения.", complete=True):
    return {"kind": "problem", "label": label, "text": text, "complete": complete}


def _ans(label, kind="number", **kw):
    return {"kind": "answer", "label": label, "answer_kind": kind, **kw}


def test_merge_prefers_complete_and_longer_duplicates():
    cut = _prob("1.1", "Тело падает", complete=False)
    full = _prob("1.1", "Тело падает с высоты 20 м. Найдите время падения.")
    problems, _ = merge([([1, 2], {"items": [cut]}), ([2, 3], {"items": [full]})])
    assert problems["1.1"]["text"] == full["text"] and problems["1.1"]["_page"] == 2


def test_candidates_need_one_number_or_formula_answer():
    book = BOOKS["zam7"]
    items = [
        _prob("1.1"),
        _prob("1.2"),
        _prob("1.3"),
        _prob("1.4", "Коротко"),
        _ans("1.1", value=2.0, unit="с"),
        _ans("1.2", "other"),  # несколько ответов или график — не берём
        _ans("1.3", value=5, unit="не единица измерения"),  # единицы не разобрать — не берём
        _ans("1.4", value=1, unit="м"),  # условие слишком короткое
    ]
    problems, answers = merge([([1], {"items": items})])
    got = candidates(book, problems, answers)
    assert [c["pid"] for c in got] == ["zam7-1-1"]
    assert got[0]["part"]["value"] == 2.0 and got[0]["part"]["unit"] == "с"


def test_parts_become_separate_problems():
    from app.tools.scan_book import part_candidates

    problems = {
        "2.1": {"text": "Поезд едет из пункта А в пункт Б. Найдите а) скорость, б) вид графика.", "_page": 5}
    }
    parts = [
        {"part": "а)", "kind": "number", "value": 48, "unit": "км/ч"},
        {"part": "б)", "kind": "text", "text": "прямая из начала координат"},
        {"part": "в)", "kind": "number", "value": 1, "unit": "не единица"},  # единицы не разобрать — не берём
    ]
    got = part_candidates(BOOKS["zam7"], problems, {"2.1": {"parts": parts, "solution": "Ход решения."}})
    assert [c["pid"] for c in got] == ["zam7-2-1-p1", "zam7-2-1-p2"]
    assert "**Часть а.**" in got[0]["statement"] and got[0]["shown"] == "2.1, а"
    assert got[1]["part"]["kind"] == "text" and got[1]["solution"].startswith("Ответ из книги: прямая")
    # один ответ без частей — обычная задача без суффикса в id
    single = part_candidates(BOOKS["zam7"], problems, {"2.1": {"parts": [{"kind": "text", "text": "вверх"}]}})
    assert single[0]["pid"] == "zam7-2-1" and single[0]["statement"] == problems["2.1"]["text"]


def test_truncation_inside_parts_is_salvaged():
    from app.tools.scan_book import parse_items

    cut = '{"answers": [{"label": "1.1", "parts": [{"part": "а", "kind": "number"}, {"part": "б", "ki'
    assert parse_items(cut)["answers"][0]["parts"] == [{"part": "а", "kind": "number"}]


def test_one_broken_record_does_not_lose_the_rest():
    from app.tools.scan_book import parse_items

    raw = '{"items": [{"kind": "answer", "label": "1.1"}, {"kind": "answer", "label": "1"2"}, {"kind": "answer", "label": "1.3"}]}'
    assert [i["label"] for i in parse_items(raw)["items"]] == ["1.1", "1.3"]


def test_book_answers_allow_for_different_constants():
    from app.tools.scan_book import BOOK_TOL, STUDENT_TOL, accept

    def check(book, mine):
        c = {"part": {"kind": "number", "value": book, "unit": "кг"}}
        return accept(c, {"value": mine}), c.get("rel_tol")

    assert check(60, 60) == (True, STUDENT_TOL)  # точное совпадение: допуск ученику на округление
    ok, tol = check(1200, 1400)  # плотность из другого справочника
    assert ok and abs(tol - BOOK_TOL) < 1e-9
    assert check(-8, 8.2)[0]  # знак зависит от выбора оси
    assert check(2.0, 2.53) == (False, None)  # 26%: это уже другой ответ
    assert check(5, None) == (False, None)


def test_recheck_restores_only_confirmed_numbers(tmp_path, monkeypatch):
    import asyncio

    from app import verify as verify_module
    from app.tools.scan_book import recheck

    async def fake(statement, unit):
        answers = {"верно": (True, 10.5), "иначе": (True, 20.0), "спор": (False, None)}
        ok, value = answers[statement]
        return verify_module.Verdict(ok, value, "other")

    monkeypatch.setattr(verify_module, "verify_answer", fake)

    def cand(pid, statement, figs=()):
        part = {"kind": "number", "value": 10.0, "unit": "м"}
        return {"pid": pid, "statement": statement, "part": part, "figs": list(figs), "state": "bad"}

    todo = [cand("a", "верно"), cand("b", "иначе"), cand("c", "спор"), cand("d", "верно", ["x.png"])]
    asyncio.run(recheck(todo, 100.0, tmp_path))
    assert [c["state"] for c in todo] == ["ok", "bad", "bad", "bad"]  # рисунок проверка не видит — не трогаем


def test_retry_uses_the_books_own_tables(tmp_path, monkeypatch):
    import asyncio

    from app.tools import scan_book as sb

    seen = []

    async def fake_solve(client, model, intro, figs, parts, cache):
        seen.append((model, intro))
        return [{"value": 100.0 if model == sb.SONNET else 1.0}]

    monkeypatch.setattr(sb, "_solve", fake_solve)
    part = {"kind": "number", "value": 100.0, "unit": "м"}
    good = {"pid": "a", "statement": "условие", "part": part, "figs": [], "state": "bad"}
    formula = {"pid": "b", "statement": "у", "part": {"kind": "formula"}, "figs": [], "state": "bad"}
    asyncio.run(sb.retry_with_tables(None, [good, formula], "g = 10 м/с²", 100.0, tmp_path))
    assert good["state"] == "ok" and formula["state"] == "bad"
    assert [m for m, _ in seen] == [sb.HAIKU, sb.SONNET]  # формулу постоянные не меняют
    assert "g = 10 м/с²" in seen[0][1] and "условие" in seen[0][1]


def test_truncated_model_output_keeps_whole_items():
    from app.tools.scan_book import parse_items

    full = '{"items": [{"kind": "answer", "label": "1.1"}, {"kind": "answer", "label": "1.2"}]}'
    assert len(parse_items("текст " + full)["items"]) == 2
    # вывод оборвался на середине третьей записи — две целые остаются
    cut = '{"items": [{"kind": "answer", "label": "1.1"}, {"kind": "answer", "label": "1.2"}, {"kind": "ans'
    assert [i["label"] for i in parse_items(cut)["items"]] == ["1.1", "1.2"]


def test_collection_is_not_a_contest():
    assert STAGE_NAMES["collection"] == "Сборник задач"
    # сборник не превращается в «олимпиаду на время»: из него не делаем вариантов
    assert all(c.stage != "collection" for c in build_contests(load_bank()).values())
