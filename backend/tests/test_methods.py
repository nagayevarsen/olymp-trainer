"""Каждая формула банка методов должна совпадать с честным перебором на маленьких случаях."""

import math

import pytest

from app.methods import METHODS, catalog_text, helper_code
from app.sandbox import run_solver, validate_code


@pytest.mark.parametrize("method", METHODS, ids=[m["id"] for m in METHODS])
def test_formula_matches_brute_force(method):
    fast = run_solver(method["code"], method["cases"], timeout=30)
    slow = run_solver(method["brute"], method["cases"], timeout=60)
    for case, f, b in zip(method["cases"], fast, slow):
        assert f["ok"], (case, f)
        assert b["ok"], (case, b)
        assert math.isclose(f["answer"], b["answer"], rel_tol=1e-9, abs_tol=1e-9), (case, f, b)


def test_methods_are_unique_and_usable_as_helpers():
    ids = [m["id"] for m in METHODS]
    assert len(ids) == len(set(ids)) >= 30
    for m in METHODS:
        assert m["id"].isidentifier() and not m["id"].startswith("_")
        validate_code(helper_code(m) + "def solve():\n    return 0\n")
    assert all(m["id"] in catalog_text() for m in METHODS)
