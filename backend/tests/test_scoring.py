from app.bank import Answer, Problem, Source
from app.scoring import base_points, dynamic_points, reward


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


def test_base_points_grow_with_stage_and_number():
    assert base_points(make(stage="school")) < base_points(make(stage="city"))
    assert base_points(make(stage="city")) < base_points(make(stage="republic"))
    assert base_points(make(number=1)) < base_points(make(number=4))
    assert base_points(make(points=777)) == 777


def test_dynamic_points():
    base = 400
    assert dynamic_points(base, 0, 0) == base  # нет данных — стартовая цена
    assert dynamic_points(base, 100, 98) < base  # почти все решили — дешевле
    assert dynamic_points(base, 100, 2) > base  # почти никто — дороже
    assert base / 2 <= dynamic_points(base, 1000, 1000) <= dynamic_points(base, 1000, 0) <= base * 2


def test_reward():
    assert reward(400, 0, False, False) == 400
    assert reward(400, 1, False, False) == 320
    assert reward(400, 3, False, False) == 160
    assert reward(400, 0, True, False) == 0  # смотрел разбор и решил оригинал
    assert reward(400, 0, True, True) == 200  # смотрел разбор, но решил новый вариант
