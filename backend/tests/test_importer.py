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
