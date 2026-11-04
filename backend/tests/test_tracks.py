"""Треки: олимпиада + этап. Разные годы одной олимпиады и этапа — один трек,
разные этапы или олимпиады — разные треки, и задачи из них не смешиваются."""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.bank import Answer, Problem, Source
from app.db import DB


def prob(pid, olympiad, stage, year):
    return Problem(
        id=pid,
        subject="math",
        topic="Комбинаторика",
        title=pid,
        statement="s",
        answer=Answer(value=1),
        source=Source(olympiad=olympiad, stage=stage, year=year, grade=8, number=1),
    )


BANK = {
    p.id: p
    for p in [
        prob("euler-reg-2023", "Олимпиада Эйлера", "region", 2023),
        prob("euler-reg-2026", "Олимпиада Эйлера", "region", 2026),
        prob("euler-dist-2025", "Олимпиада Эйлера", "distance", 2025),
        prob("rk-rep-2024", "Олимпиада РК", "republic", 2024),
    ]
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "load_bank", lambda: BANK)
    monkeypatch.setattr(main, "get_problem", BANK.get)
    main.set_db(DB(":memory:"))
    return TestClient(main.app)


def track_of(client, olympiad, stage_name):
    return next(
        t for t in client.get("/api/tracks").json() if t["olympiad"] == olympiad and t["stage"] == stage_name
    )


def test_same_olympiad_and_stage_different_years_is_one_track(client):
    tracks = client.get("/api/tracks").json()
    assert len(tracks) == 3
    euler_reg = track_of(client, "Олимпиада Эйлера", "Региональный (областной) этап")
    assert euler_reg["count"] == 2 and euler_reg["years"] == [2023, 2026]


def test_problems_of_track_are_not_mixed(client):
    euler_reg = track_of(client, "Олимпиада Эйлера", "Региональный (областной) этап")
    ids = {p["id"] for p in client.get(f"/api/problems?track={euler_reg['id']}").json()}
    assert ids == {"euler-reg-2023", "euler-reg-2026"}  # без дистанционного этапа и без олимпиады РК


def test_recommendations_stay_in_track(client):
    uid = client.post("/api/users", json={"name": "x"}).json()["id"]
    dist = track_of(client, "Олимпиада Эйлера", "Дистанционный этап")
    me = client.get(f"/api/me?track={dist['id']}", headers={"X-User-Id": uid}).json()
    assert [r["id"] for r in me["recommended"]] == ["euler-dist-2025"]
