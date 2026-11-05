import pytest

from app.sandbox import run_solver
from app.verify import Attempt, decide, run_program


def A(*xs):
    return [Attempt(f"m{i}", x) for i, x in enumerate(xs)]


TOL = 1e-6


def test_risky_needs_two_agreeing_programs_and_majority():
    assert decide("enumeration", A(14, 14, 12), A(14, 14), TOL) == (True, 14, "")
    ok, _, reason = decide("enumeration", A(14, 14, 14), A(14, 13), TOL)
    assert not ok and "разошлись" in reason
    ok, _, _ = decide("enumeration", A(14, 14, 14), A(14, None), TOL)
    assert not ok  # одна программа — мало


def test_risky_programs_against_reasoning_majority_is_rejected():
    ok, _, _ = decide("graph_plot", A(3, 4, 4), A(3, 3), TOL)
    assert not ok
    ok, _, _ = decide("graph_theory", A(3, None, None), A(3, 3), TOL)
    assert not ok  # за ответ меньше двух решений


def test_escalation_can_break_a_tie_but_not_alone():
    # Haiku-программа ошиблась, Gemini и Sonnet совпали, решения за 14 — принимаем
    assert decide("enumeration", A(14, 14, 13, 14), A(13, 14, 14), TOL)[0]
    # Только Sonnet за 14 — недостаточно
    assert not decide("enumeration", A(13, 12, 11, 14), A(13, 12, 14), TOL)[0]


def test_other_needs_unanimous_reasoning_and_program():
    assert decide("other", A(2.5, 2.5, 2.5), A(2.5, None), TOL) == (True, 2.5, "")
    assert not decide("other", A(2.5, 2.5, 3), A(2.5, 2.5), TOL)[0]
    assert not decide("other", A(2.5, 2.5, 2.5), A(None, None), TOL)[0]
    assert not decide("other", A(2.5, 2.5, 2.5), A(2.5, 7), TOL)[0]
    # после эскалации: 3 из 4 решений за ответ, программы согласны
    assert decide("other", A(2.5, 2.5, 3, 2.5), A(2.5, 2.5, 2.5), TOL)[0]


def test_physics_tolerance():
    assert decide("other", A(9.81, 9.8, 9.79), A(9.8), 0.01)[0]


def test_brute_force_sandbox_features():
    code = (
        "def solve():\n"
        "    c = 0\n"
        "    for p in permutations(range(1, 6)):\n"
        "        if all(abs(p[i] - p[i + 1]) != 1 for i in range(4)):\n"
        "            c += 1\n"
        "    digits = set(int(d) for d in str(2**20))\n"
        "    return c * 100 + len(digits)\n"
    )
    assert run_solver(code, [{}], timeout=30)[0]["answer"] == 1407


@pytest.mark.parametrize(
    "code,expect_none",
    [
        ("def solve():\n    return -123456789\n", True),
        ("def solve():\n    x = []\n    x.append(1)\n    return 1\n", True),
        ("def solve():\n    return sum(1 for a, b in product(range(10), repeat=2) if a < b)\n", False),
    ],
)
def test_run_program(code, expect_none):
    value, _ = run_program(code)
    assert (value is None) == expect_none


def test_sandbox_allows_set_union_underscore_and_is_not():
    code = (
        "def solve():\n"
        "    s = set()\n"
        "    best = None\n"
        "    for _ in range(3):\n"
        "        for a in range(5):\n"
        "            s = s | {a % 3}\n"
        "            if best is None or a > best:\n"
        "                best = a\n"
        "    return len(s) * 10 + best\n"
    )
    assert run_solver(code, [{}])[0]["answer"] == 34


def test_sandbox_still_blocks_dunder_names():
    from app.sandbox import SandboxError, validate_code

    with pytest.raises(SandboxError):
        validate_code("def solve():\n    return __builtins__\n")


def test_extract_json_takes_first_object():
    from app.llm import extract_json

    assert extract_json('{"answer": 5}\n{"answer": 6}') == {"answer": 5}


def test_program_can_call_method_bank():
    # перебор на маленьких n сверяется с формулой Гаусса из банка, затем ответ для большого n
    code = (
        "def solve():\n"
        "    def brute(n):\n"
        "        return sum(range(1, n + 1))\n"
        "    for n in range(1, 30):\n"
        "        if gauss_sum(1, 1, n) != brute(n):\n"
        "            return -123456789\n"
        "    return gauss_sum(1, 1, 10**9)\n"
    )
    value, note = run_program(code)
    assert value == 10**9 * (10**9 + 1) // 2, note


def test_prompt_contains_method_catalog():
    from app.verify import LARGE, METHOD

    text = METHOD["enumeration"].replace("{large}", LARGE.format(catalog="CATALOG"))
    assert "brute(n)" in text and "CATALOG" in text
