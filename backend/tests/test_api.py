"""Сквозной сценарий через HTTP API (без обращения к ИИ: у демо-задач подсказки уже есть)."""

import pytest
from fastapi.testclient import TestClient

from app.bank import get_problem, load_bank
from app.checker import format_number
from app.cloner import make_variant
from app.db import DB
from app.main import app, set_db


@pytest.fixture
def client():
    set_db(DB(":memory:"))
    return TestClient(app)


def new_user(client, name="Аян"):
    token = client.post("/api/users", json={"name": name, "grade": 7}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/api/health").json()["ok"]


def test_list_has_points_not_difficulty_labels(client):
    items = client.get("/api/problems").json()
    assert items and all(isinstance(i["points"], int) for i in items)
    assert all("difficulty" not in i for i in items)
    assert all(i["solve_rate"] is None for i in items)  # до решения процент не показываем


def test_full_flow(client):
    h = new_user(client)
    pid = "demo-phys-throw"
    detail = client.get(f"/api/problems/{pid}", headers=h).json()
    points = detail["points"]
    assert detail["needs_unit"] and detail["hints_opened"] == []

    # неверная размерность
    r = client.post(f"/api/problems/{pid}/check", json={"answer": "4 м"}, headers=h).json()
    assert r["status"] == "wrong_dimension" and r["earned"] == 0

    # подсказки открываются по порядку
    assert client.post(f"/api/problems/{pid}/hints/2", headers=h).status_code == 400
    points = client.get(f"/api/problems/{pid}", headers=h).json()["points"]  # цена чуть выросла после ошибки
    hint = client.post(f"/api/problems/{pid}/hints/1", headers=h).json()
    assert hint["text"] and hint["potential"] == max(1, round(points * 0.8))

    r = client.post(f"/api/problems/{pid}/check", json={"answer": "4 с"}, headers=h).json()
    assert r["correct"] and r["first_solve"] and r["earned"] == max(1, round(points * 0.8))
    assert r["solve_rate"] == 100

    # повторное решение баллов не даёт
    r2 = client.post(f"/api/problems/{pid}/check", json={"answer": "4 с"}, headers=h).json()
    assert r2["correct"] and r2["earned"] == 0 and r2["already_solved"]

    me = client.get("/api/me", headers=h).json()
    assert me["points"] == r["earned"] and me["solved"] == 1 and me["rank"] == 1


def test_solution_then_variant_gives_half(client):
    h = new_user(client)
    pid = "demo-phys-avg-speed"
    points = client.get(f"/api/problems/{pid}", headers=h).json()["points"]
    sol = client.post(f"/api/problems/{pid}/solution", headers=h).json()
    assert "48" in sol["solution"] and sol["can_clone"]

    # оригинал после разбора — 0 баллов
    v = client.post(f"/api/problems/{pid}/variant", json={}).json()
    variant = make_variant(get_problem(pid), v["seed"])
    ans = f"{format_number(variant.answer.value)} км/ч"
    r = client.post(f"/api/problems/{pid}/check", json={"answer": ans, "seed": v["seed"]}, headers=h).json()
    assert r["correct"] and r["earned"] == max(1, round(points * 0.5))


def test_variant_detail_shows_new_statement(client):
    v = client.post("/api/problems/demo-math-tournament/variant", json={"seed": 5}).json()
    d = client.get(f"/api/problems/demo-math-tournament?seed={v['seed']}").json()
    # задача олимпиады: в тренировке показываем аналог, оригинал не выдаём (он остаётся для тура)
    assert d["statement"] == v["statement"] and d["analogue_only"] and d["original_statement"] is None
    assert d["verification"]["reproduces_original"]


def test_only_olympiad_problems_with_template_are_replaced_by_analogue(client):
    bank = load_bank().values()
    book = next(p for p in bank if p.source.stage == "collection")
    no_template = next(p for p in bank if p.source.stage != "collection" and not p.can_clone)
    assert client.get(f"/api/problems/{book.id}").json()["analogue_only"] is False
    assert client.get(f"/api/problems/{no_template.id}").json()["analogue_only"] is False


def test_check_requires_user(client):
    r = client.post("/api/problems/demo-phys-throw/check", json={"answer": "4 с"})
    assert r.status_code == 401


def test_unknown_problem(client):
    assert client.get("/api/problems/nope").status_code == 404


def test_leaderboard(client):
    h1, _ = new_user(client, "А"), new_user(client, "Б")
    client.post("/api/problems/demo-math-tournament/check", json={"answer": "66"}, headers=h1)
    board = client.get("/api/leaderboard").json()
    assert board[0]["place"] == 1 and board[0]["points"] > 0
    assert all(r["name"] is None and r["grade"] is None for r in board)  # чужих ников и классов нет
    mine = client.get("/api/leaderboard", headers=h1).json()
    assert [r["name"] for r in mine if r["me"]] == ["А"]
