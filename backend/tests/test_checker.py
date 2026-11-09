import pytest

from app.checker import AnswerKey, check_answer, format_number, split_answer
from app.mathparse import ParseError, parse_number
from app.units import UnitError, describe_dim, parse_unit


@pytest.mark.parametrize(
    "s, expected",
    [
        ("4", 4),
        ("1,5", 1.5),
        ("-3", -3),
        ("−3", -3),
        ("3/4", 0.75),
        ("2√3", 2 * 3**0.5),
        ("√(16)", 4),
        ("2pi", 2 * 3.141592653589793),
        ("2π", 2 * 3.141592653589793),
        ("1.2e3", 1200),
        ("2^10", 1024),
        ("2·3", 6),
        ("sqrt(2)*sqrt(2)", 2),
    ],
)
def test_parse_number(s, expected):
    assert parse_number(s) == pytest.approx(expected)


@pytest.mark.parametrize(
    "s", ["", "abc", "__import__('os')", "9^9^9^9", "2^99999", "x+1", "open(1)", "1e", "e"]
)
def test_parse_number_rejects(s):
    with pytest.raises(ParseError):
        parse_number(s)


@pytest.mark.parametrize(
    "unit, factor",
    [
        ("м", 1),
        ("км", 1000),
        ("см", 0.01),
        ("мм", 0.001),
        ("мкм", 1e-6),
        ("с", 1),
        ("мс", 1e-3),
        ("мин", 60),
        ("ч", 3600),
        ("кг", 1),
        ("г", 1e-3),
        ("т", 1000),
        ("км/ч", 1000 / 3600),
        ("м/с²", 1),
        ("м/с^2", 1),
        ("кДж", 1000),
        ("МДж", 1e6),
        ("кОм", 1000),
        ("мА", 1e-3),
        ("мкФ", 1e-6),
        ("пФ", 1e-12),
        ("km/h", 1000 / 3600),
        ("kJ", 1000),
        ("Н·м", 1),
        ("Н м", 1),
        ("Н/(м·с)", 1),
    ],
)
def test_units_factor(unit, factor):
    assert parse_unit(unit).factor == pytest.approx(factor)


def test_units_dimensions():
    assert parse_unit("Дж").dim == parse_unit("Н·м").dim == parse_unit("кг·м²/с²").dim
    assert parse_unit("Вт").dim == parse_unit("Дж/с").dim
    assert parse_unit("км/ч").dim == parse_unit("м/с").dim
    assert parse_unit("Па").dim == parse_unit("Н/м²").dim
    assert parse_unit("Ом").dim == parse_unit("В/А").dim
    assert describe_dim(parse_unit("м/с").dim) == "скорость"
    assert describe_dim(parse_unit("м/с²").dim) == "ускорение"


@pytest.mark.parametrize("bad", ["абв", "м/", "кг**", "м)"])
def test_units_reject(bad):
    with pytest.raises(UnitError):
        parse_unit(bad)


def test_split_answer():
    assert split_answer("4,5 м/с") == ("4,5", "м/с")
    assert split_answer("4с") == ("4", "с")
    assert split_answer("2√3 м") == ("2√3", "м")
    assert split_answer("2 sqrt(3) м") == ("2 sqrt(3)", "м")
    assert split_answer("17") == ("17", "")


class TestCheck:
    time_key = AnswerKey(4, "с")

    def test_correct(self):
        assert check_answer(self.time_key, "4 с").status == "correct"
        assert check_answer(self.time_key, "4,0с").status == "correct"

    def test_unit_conversion(self):
        assert check_answer(self.time_key, "4000 мс").status == "correct"
        assert check_answer(AnswerKey(48, "км/ч"), "13,333 м/с").status == "correct"
        assert check_answer(AnswerKey(672, "кДж"), "672000 Дж").status == "correct"

    def test_wrong_dimension_is_explained(self):
        r = check_answer(self.time_key, "4 м")
        assert r.status == "wrong_dimension"
        assert "длина" in r.message and "время" in r.message

    def test_wrong_number(self):
        assert check_answer(self.time_key, "5 с").status == "wrong"

    def test_missing_unit_counts_but_warns(self):
        r = check_answer(self.time_key, "4")
        assert r.status == "unit_missing" and r.correct

    def test_tolerance(self):
        assert check_answer(AnswerKey(2.5, "см"), "2,52 см").correct
        assert not check_answer(AnswerKey(2.5, "см"), "2,6 см").correct

    def test_math_answers(self):
        key = AnswerKey(467, rel_tol=1e-9)
        assert check_answer(key, "467").correct
        assert not check_answer(key, "468").correct
        assert check_answer(AnswerKey(2 * 3**0.5), "2√3").correct

    def test_percent(self):
        key = AnswerKey(75, "%")
        assert check_answer(key, "75%").correct
        assert check_answer(key, "75 %").correct
        assert check_answer(key, "75").correct

    def test_unparsable(self):
        assert check_answer(self.time_key, "четыре").status == "unparsable"


def test_format_number():
    assert format_number(12.0) == "12"
    assert format_number(0.125) == "0,125"
    assert format_number(2.5) == "2,5"


def test_compound_time_is_accepted_and_clock_notation_is_not():
    key = AnswerKey(640, "мин")
    for good in ("10 часов 40 минут", "10 ч 40 мин", "10ч40мин", "640 мин", "10,6667 ч"):
        assert check_answer(key, good).correct, good
    assert check_answer(key, "10:40").status == "unparsable"
    assert not check_answer(key, "10 ч").correct
    assert check_answer(AnswerKey(4, "м"), "4 м").correct  # не время — как раньше
