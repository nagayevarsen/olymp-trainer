"""Песочница для кода-решателя задач.

Решатели (функция solve(...)) пишет человек или ИИ. Перед запуском код
проверяется по белому списку конструкций AST: нет импортов, атрибутов,
«дандер»-имён, while-циклов, определений классов. Затем он исполняется
в отдельном процессе Python с таймаутом, чтобы зацикливание или тяжёлые
вычисления не повесили сервер.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from typing import Any

SAFE_FUNCS = {
    "abs",
    "min",
    "max",
    "round",
    "int",
    "float",
    "sum",
    "len",
    "range",
    "pow",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "log",
    "log2",
    "log10",
    "exp",
    "floor",
    "ceil",
    "factorial",
    "comb",
    "perm",
    "gcd",
    "lcm",
    "isqrt",
    "radians",
    "degrees",
    "hypot",
    "all",
    "any",
    "sorted",
    "divmod",
    "bool",
}
SAFE_CONSTS = {"pi", "e", "True", "False", "None"}

_ALLOWED_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.Expr,
    ast.If,
    ast.For,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.keyword,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Subscript,
    ast.ListComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)

MAX_CODE_LEN = 4000
TIMEOUT_S = 5.0


class SandboxError(ValueError):
    pass


def validate_code(code: str, entry: str = "solve") -> None:
    """Проверить, что код безопасен и определяет функцию entry. Иначе SandboxError."""
    if len(code) > MAX_CODE_LEN:
        raise SandboxError("Код слишком длинный")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxError(f"Синтаксическая ошибка: {exc.msg}") from exc

    defined: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise SandboxError(f"Запрещённая конструкция: {type(node).__name__}")
        if isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                raise SandboxError("Декораторы запрещены")
            defined.add(node.name)
            defined.update(a.arg for a in node.args.args)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        if isinstance(node, ast.arg):
            defined.add(node.arg)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise SandboxError("Имена с подчёркиванием запрещены")
            if isinstance(node.ctx, ast.Load) and node.id not in defined | SAFE_FUNCS | SAFE_CONSTS:
                raise SandboxError(f"Неизвестное имя: {node.id}")
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
            raise SandboxError("Разрешены только прямые вызовы функций")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 200:
            raise SandboxError("Слишком длинная строка")

    top = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not any(f.name == entry for f in top):
        raise SandboxError(f"Нет функции {entry}(...)")


def validate_expression(expr: str, names: list[str] | tuple[str, ...] = ()) -> None:
    """Проверить выражение-ограничение вроде "answer > 0 and v < 100"."""
    args = ", ".join(["answer", *names])
    validate_code(f"def check({args}):\n    return ({expr})\n", entry="check")


# Код, который выполняется в дочернем процессе. Получает JSON на stdin.
_RUNNER = r"""
import json, math, sys
safe = {n: getattr(math, n) for n in (
    "sqrt sin cos tan asin acos atan atan2 log log2 log10 exp floor ceil factorial comb perm "
    "gcd lcm isqrt radians degrees hypot pi e").split()}
for n in ("abs min max round int float sum len range pow all any sorted divmod bool").split():
    safe[n] = __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
req = json.load(sys.stdin)
g = {"__builtins__": {}}
g.update(safe)
exec(compile(req["code"], "<solver>", "exec"), g)
out = []
for params in req["calls"]:
    try:
        res = g["solve"](**params)
        ok = {"ok": True, "answer": float(res)}
        if req.get("constraints"):
            env = dict(g); env.update(params); env["answer"] = float(res)
            failed = [c for c in req["constraints"] if not eval(c, env)]
            if failed:
                ok = {"ok": False, "error": "constraint: " + failed[0], "answer": float(res)}
        out.append(ok)
    except Exception as exc:
        out.append({"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200]})
json.dump(out, sys.stdout)
"""


def _limit_memory() -> None:
    import resource

    limit = 512 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_solver(
    code: str, calls: list[dict[str, Any]], constraints: list[str] | None = None
) -> list[dict[str, Any]]:
    """Запустить solve(**params) для каждого набора params. Возвращает список
    {"ok": bool, "answer": float, "error": str}."""
    validate_code(code)
    names = list(calls[0]) if calls else []
    for c in constraints or []:
        validate_expression(c, names)
    payload = json.dumps({"code": code, "calls": calls, "constraints": constraints or []})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _RUNNER],
            input=payload,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            preexec_fn=_limit_memory if sys.platform.startswith("linux") else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError("Решатель работает слишком долго") from exc
    if proc.returncode != 0:
        last = proc.stderr.strip().splitlines()[-1:] or ["неизвестная ошибка"]
        raise SandboxError(f"Решатель упал: {last[0][:200]}")
    return json.loads(proc.stdout)
