import pytest

from app.sandbox import SandboxError, run_solver, validate_code


def test_runs_simple_solver():
    code = "def solve(a, b):\n    return a * b + sqrt(16)\n"
    res = run_solver(code, [{"a": 2, "b": 3}, {"a": 1, "b": 1}])
    assert [r["answer"] for r in res] == [10.0, 5.0]


def test_constraints():
    code = "def solve(v1, v2):\n    return 2 * v1 * v2 / (v1 + v2)\n"
    res = run_solver(code, [{"v1": 60, "v2": 40}, {"v1": 50, "v2": 50}], ["v1 != v2"])
    assert res[0]["ok"] and not res[1]["ok"]


def test_runtime_error_is_reported_not_raised():
    res = run_solver("def solve(a):\n    return 1 / a\n", [{"a": 0}])
    assert not res[0]["ok"] and "ZeroDivisionError" in res[0]["error"]


@pytest.mark.parametrize(
    "code",
    [
        "import os\ndef solve():\n    return 1\n",
        "def solve():\n    return __import__('os').system('ls')\n",
        "def solve():\n    return (1).__class__\n",
        "def solve():\n    return open('/etc/passwd')\n",
        "def solve():\n    return eval('1')\n",
        "def solve():\n    while True:\n        pass\n",
        "class X: pass\ndef solve():\n    return 1\n",
        "def solve():\n    return [].append(1)\n",
        "def other():\n    return 1\n",
    ],
)
def test_rejects_dangerous_code(code):
    with pytest.raises(SandboxError):
        validate_code(code)


def test_timeout():
    code = "def solve():\n    s = 0\n    for i in range(10**12):\n        s += i\n    return s\n"
    with pytest.raises(SandboxError):
        run_solver(code, [{}])
