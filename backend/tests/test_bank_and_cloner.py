"""Проверка всего банка задач: каждый шаблон обязан воспроизводить официальный ответ.
Этот тест запускается в CI — сломанная задача не попадёт в приложение."""

import pytest

from app.bank import load_bank
from app.checker import check_answer, format_number
from app.cloner import make_variant, verify_template

BANK = load_bank()


def test_bank_not_empty():
    assert len(BANK) >= 5
    assert {p.subject for p in BANK.values()} == {"math", "physics"}


@pytest.mark.parametrize("pid", sorted(BANK))
def test_template_reproduces_official_answer(pid):
    p = BANK[pid]
    if not p.template:
        pytest.skip("без шаблона")
    report = verify_template(p, p.template)
    assert report.ok, report.errors
    assert p.template.verification.reproduces_original, "запустите bank_tool check --fix"


@pytest.mark.parametrize("pid", sorted(BANK))
def test_hints_present(pid):
    p = BANK[pid]
    assert p.hints is None or len(p.hints.steps) == 3


def test_variant_is_deterministic_and_differs():
    p = BANK["demo-phys-throw"]
    v1, v2 = make_variant(p, 42), make_variant(p, 42)
    assert v1.statement == v2.statement and v1.answer.value == v2.answer.value
    assert v1.statement != p.statement


def test_variant_answer_is_checkable():
    p = BANK["demo-phys-avg-speed"]
    v = make_variant(p, 7)
    raw = f"{format_number(v.answer.value)} км/ч"
    assert check_answer(v.answer, raw).correct


def test_variant_respects_constraints():
    p = BANK["demo-phys-avg-speed"]
    for seed in range(1, 15):
        v = make_variant(p, seed)
        assert v.params["v1"] != v.params["v2"]
        assert v.answer.value * 10 == pytest.approx(round(v.answer.value * 10))


def test_integer_answers_for_integer_templates():
    p = BANK["demo-math-divisible"]
    for seed in range(1, 10):
        v = make_variant(p, seed)
        assert v.answer.value == int(v.answer.value)
        assert v.params["b"] % v.params["a"] != 0
