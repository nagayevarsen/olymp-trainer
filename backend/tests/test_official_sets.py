"""Олимпиада на время: состав официального варианта, равные баллы городских этапов, туры и поиск сборников."""

from app import contests, olympiad_rules
from app.bank import load_bank
from app.routes.olympiads import EQUAL_POINTS, _completeness, contest_points


def test_official_sets_come_from_documents():
    smag = "Олимпиада им. Шалтая Смагулова"
    assert olympiad_rules.official_set(smag, "city", 1).problems == 20
    assert olympiad_rules.official_set(smag, "city", 2).problems == 5
    other_tour = olympiad_rules.official_set(
        smag, "city", 3
    )  # число задач не подтверждено, но все равноценны
    assert other_tour.problems is None and other_tour.equal_weight
    zhaut = olympiad_rules.official_set("Городская Жаутыковская олимпиада (Алматы)", "city")
    assert zhaut.problems is None and zhaut.equal_weight  # число задач берётся со страницы источника
    assert olympiad_rules.official_set("Международная Жаутыковская олимпиада (IZhO)", "international") is None


def test_smagulov_time_belongs_to_the_five_problem_tour_only():
    smag = "Олимпиада им. Шалтая Смагулова"
    assert olympiad_rules.rule_for(smag, "city", "math", 7, 2).minutes == 180
    assert (
        olympiad_rules.rule_for(smag, "city", "math", 7, 1) is None
    )  # у 1 тура (20 задач) времени в документах нет
    assert olympiad_rules.rule_for(smag, "city", "math").minutes == 180  # тур неизвестен — как раньше


def test_available_list_names_only_olympiads_with_a_complete_variant():
    assert "Смагуловская (городской этап)" in olympiad_rules.available_list()
    only_euler = olympiad_rules.available_list({"Олимпиада им. Леонарда Эйлера"})
    assert only_euler == ["Эйлера (региональный и заключительный этапы)"]


def test_tours_of_matol_olympiads_are_separate_contests():
    bank = load_bank()
    for c in contests.build_contests(bank).values():
        if c.olympiad.startswith(("Олимпиада им. Шалтая", "Городская Жаутыковская")):
            assert c.tour is not None, c.id
            assert {contests.tour_of(p) for p in c.problems} == {c.tour}, c.id  # туры не смешиваются


def test_city_olympiads_have_equal_points_and_short_variants_are_marked():
    seen = set()
    for c in contests.build_contests(load_bank()).values():
        if not c.olympiad.startswith(("Олимпиада им. Шалтая", "Городская Жаутыковская")):
            continue
        assert set(contest_points(c)) == {EQUAL_POINTS}, c.id
        info = _completeness(c)
        assert info["equal_weight"]
        if info["official_count"]:
            assert info["complete"] == (
                len({p.source.number or p.id for p in c.problems}) == info["official_count"]
            )
        seen.add(c.olympiad[:12])
    assert len(seen) == 2


def test_collections_are_found_by_a_generic_word():
    bank = load_bank()
    book = bank["zam7-1-5"]
    assert contests.matches(book, "сборник") and contests.matches(book, "нестандартные задачи")
    gel = bank["gelfgat-6-28"]
    assert contests.matches(gel, "сборник физика")
    olympiad = next(p for p in bank.values() if p.source.olympiad.startswith("Олимпиада им. Леонарда Эйлера"))
    assert not contests.matches(olympiad, "сборник")
