from app.bank import Answer, Problem, Source
from app.scoring import MAX_POINTS, MIN_POINTS, base_points, dynamic_points, reward, scale_for_contest


def make(stage="republic", grade=9, number=3, points=None):
    return Problem(
        id="x",
        subject="math",
        topic="t",
        title="t",
        statement="s",
        answer=Answer(value=1),
        source=Source(olympiad="o", stage=stage, grade=grade, number=number),
        points=points,
    )


def test_base_points_grow_with_stage_and_number_within_3_to_10():
    assert base_points(make(stage="school")) < base_points(make(stage="city"))
    assert base_points(make(stage="city")) < base_points(make(stage="republic"))
    assert base_points(make(number=1)) < base_points(make(number=5))
    assert base_points(make(points=7)) == 7
    for st in ("school", "international"):
        for n in (1, 9):
            assert MIN_POINTS <= base_points(make(stage=st, number=n, grade=11)) <= MAX_POINTS


def test_dynamic_points():
    base = 6
    assert dynamic_points(base, 0, 0) == base  # нет данных — стартовая цена
    assert dynamic_points(base, 100, 98) < base  # почти все решили — дешевле
    assert dynamic_points(base, 100, 2) > base  # почти никто — дороже
    assert base - 2 <= dynamic_points(base, 1000, 1000) <= dynamic_points(base, 1000, 0) <= base + 2
    assert dynamic_points(10, 1000, 0) == 10 and dynamic_points(3, 1000, 1000) == 3


def test_reward():
    assert reward(10, 0, False, False) == 10
    assert reward(10, 1, False, False) == 8
    assert reward(10, 3, False, False) == 4
    assert reward(3, 3, False, False) == 1
    assert reward(10, 0, True, False) == 0  # смотрел разбор и решил оригинал
    assert reward(10, 0, True, True) == 5  # смотрел разбор, но решил новый вариант


def test_contest_scale_hardest_10_easiest_3():
    assert scale_for_contest([4, 5, 7]) == [3, 5, 10]
    assert scale_for_contest([6]) == [10]
    assert scale_for_contest([]) == []
