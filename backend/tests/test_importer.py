import pytest

from app.importer import ImportError_, _get, answer_in_text


def test_answer_found_in_pdf_text():
    text = "Ответ: 𝑡2 = 26,3 с. Критерии ... плотность 1,34 г/см3, всего 142 м"
    assert answer_in_text(26.3, text)
    assert answer_in_text(1.34, text)
    assert answer_in_text(142, text)


def test_invented_answer_rejected():
    text = "Ответ: 1420 м, задача 26, 3 балла"
    assert not answer_in_text(142, text)  # 142 — часть другого числа
    assert not answer_in_text(26.3, text)  # «26, 3» — не то же самое


def test_untrusted_site_is_never_downloaded():
    with pytest.raises(ImportError_):
        _get("https://random-site.example/problems.pdf")


def test_multi_part_problem_is_split_into_parts():
    from app.importer import expand_parts

    items = [
        {"number": "2", "kind": "numeric", "statement": "Одна задача", "answer_value": 5},
        {
            "number": "3",
            "kind": "multi",
            "has_figure": False,
            "title": "Маятник",
            "statement": "Маятник длиной 1 м.",
            "parts": [
                {
                    "label": "A.1",
                    "question": "Найдите период.",
                    "kind": "numeric",
                    "answer_value": 2.0,
                    "answer_unit": "с",
                },
                {"label": "A.2", "question": "Докажите формулу.", "kind": "proof", "answer_value": None},
                {
                    "label": "B",
                    "question": "По графику…",
                    "kind": "numeric",
                    "has_figure": True,
                    "answer_value": 3,
                },
            ],
        },
    ]
    out = expand_parts(items)
    assert len(out) == 4
    a1 = out[1]
    assert a1["part"] == "A.1" and a1["answer_value"] == 2.0 and a1["answer_unit"] == "с"
    assert a1["statement"].startswith("Маятник длиной 1 м.") and "Пункт A.1" in a1["statement"]
    assert out[2]["kind"] == "proof"
    assert out[3]["has_figure"] is True


def test_pdf_inside_zip(tmp_path, monkeypatch):
    import io
    import zipfile

    from app import importer

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2006/Theo_solution 1.pdf", b"%PDF-1.4 test")
        z.writestr("2006/readme.txt", b"x")

    class Resp:
        content = buf.getvalue()

    monkeypatch.setattr(importer, "raw_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "_get", lambda url: Resp())
    url = "https://www.ipho-new.org/download/552/"
    assert importer.zip_members(url) == ["2006/Theo_solution 1.pdf"]
    path = importer.fetch_pdf(url + "#member=2006/Theo_solution 1.pdf")
    assert path.read_bytes().startswith(b"%PDF")
    import pytest

    with pytest.raises(importer.ImportError_):
        importer.fetch_pdf(url + "#member=../../etc/passwd")
