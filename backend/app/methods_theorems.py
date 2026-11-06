"""Теоремы и формулы олимпиадной математики и физики — продолжение банка методов (app/methods.py).

Формат тот же: code — формула или утверждение теоремы, brute — независимое вычисление
по определению (перебор, координаты, моделирование). Тест tests/test_methods.py сверяет их
на маленьких случаях, поэтому неверная формула в банк не попадёт.
Песочница: без while, без методов объектов (.append и т. п.), без import.
"""

from __future__ import annotations

_TRI = [(3, 4, 5), (5, 5, 6), (7, 8, 9), (4, 6, 7), (6, 6, 6), (5, 12, 13), (8, 15, 17), (9, 10, 11)]

# Координаты треугольника по сторонам: C=(0,0), B=(a,0), A по теореме косинусов (для brute).
_COORDS = (
    "    cx, cy = 0.0, 0.0\n"
    "    bx, by = float(a), 0.0\n"
    "    ax = (a * a + b * b - c * c) / (2 * a)\n"
    "    ay = sqrt(max(b * b - ax * ax, 0.0))\n"
)
# Центр описанной окружности по координатам (для brute).
_CIRCUM = (
    "    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))\n"
    "    ox = ((ax*ax+ay*ay)*(by-cy) + (bx*bx+by*by)*(cy-ay) + (cx*cx+cy*cy)*(ay-by)) / d\n"
    "    oy = ((ax*ax+ay*ay)*(cx-bx) + (bx*bx+by*by)*(ax-cx) + (cx*cx+cy*cy)*(bx-ax)) / d\n"
)

THEOREMS: list[dict] = [
    # ---------- Геометрия: теоремы ----------
    {
        "id": "pythagoras",
        "name": "Теорема Пифагора",
        "area": "геометрия",
        "when": "прямоугольный треугольник: гипотенуза по катетам; расстояние между точками на плоскости",
        "formula": "c = √(a² + b²)",
        "code": "def solve(a, b):\n    return sqrt(a * a + b * b)\n",
        "brute": "def solve(a, b):\n    return hypot(float(a) - 0.0, 0.0 - float(b))\n",
        "cases": [{"a": a, "b": b} for a in (1, 3, 5, 8) for b in (2, 4, 7, 15)],
    },
    {
        "id": "law_of_cosines",
        "name": "Теорема косинусов",
        "area": "геометрия",
        "when": "известны две стороны и угол между ними (в градусах) — найти третью сторону",
        "formula": "c² = a² + b² − 2ab·cos γ",
        "code": "def solve(a, b, gamma):\n    return sqrt(a*a + b*b - 2*a*b*cos(radians(gamma)))\n",
        "brute": "def solve(a, b, gamma):\n    x, y = a * cos(radians(gamma)), a * sin(radians(gamma))\n"
        "    return hypot(x - b, y)\n",
        "cases": [
            {"a": a, "b": b, "gamma": g} for a in (2, 5) for b in (3, 7) for g in (30, 60, 90, 120, 150)
        ],
    },
    {
        "id": "circumradius",
        "name": "Радиус описанной окружности (теорема синусов)",
        "area": "геометрия",
        "when": "известны три стороны треугольника; a / sin α = 2R",
        "formula": "R = abc / (4S), S — по формуле Герона",
        "code": "def solve(a, b, c):\n    p = (a + b + c) / 2\n    s = sqrt(p * (p - a) * (p - b) * (p - c))\n"
        "    return a * b * c / (4 * s)\n",
        "brute": "def solve(a, b, c):\n" + _COORDS + _CIRCUM + "    return hypot(ax - ox, ay - oy)\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "inradius",
        "name": "Радиус вписанной окружности",
        "area": "геометрия",
        "when": "известны три стороны треугольника",
        "formula": "r = S / p, p — полупериметр",
        "code": "def solve(a, b, c):\n    p = (a + b + c) / 2\n    return sqrt(p * (p - a) * (p - b) * (p - c)) / p\n",
        "brute": "def solve(a, b, c):\n" + _COORDS + "    ix = (a * ax + b * bx + c * cx) / (a + b + c)\n"
        "    iy = (a * ay + b * by + c * cy) / (a + b + c)\n    return iy\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "median_length",
        "name": "Длина медианы",
        "area": "геометрия",
        "when": "медиана к стороне a по трём сторонам",
        "formula": "m_a = ½·√(2b² + 2c² − a²)",
        "code": "def solve(a, b, c):\n    return sqrt(2 * b * b + 2 * c * c - a * a) / 2\n",
        "brute": "def solve(a, b, c):\n" + _COORDS + "    return hypot(ax - a / 2, ay)\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "bisector_length",
        "name": "Длина биссектрисы",
        "area": "геометрия",
        "when": "биссектриса угла A (к стороне a) по трём сторонам; делит a в отношении b : c",
        "formula": "l_a = √(bc·((b + c)² − a²)) / (b + c)",
        "code": "def solve(a, b, c):\n    return sqrt(b * c * ((b + c) ** 2 - a * a)) / (b + c)\n",
        "brute": "def solve(a, b, c):\n"
        + _COORDS
        + "    t = b / (b + c)\n    dx, dy = cx + (bx - cx) * t, cy + (by - cy) * t\n    return hypot(ax - dx, ay - dy)\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "euler_oi",
        "name": "Формула Эйлера для расстояния между центрами вписанной и описанной окружностей",
        "area": "геометрия",
        "when": "расстояние OI в треугольнике; отсюда неравенство Эйлера R ≥ 2r",
        "formula": "OI² = R² − 2Rr",
        "code": "def solve(a, b, c):\n    p = (a + b + c) / 2\n    s = sqrt(p * (p - a) * (p - b) * (p - c))\n"
        "    R, r = a * b * c / (4 * s), s / p\n    return R * R - 2 * R * r\n",
        "brute": "def solve(a, b, c):\n"
        + _COORDS
        + _CIRCUM
        + "    ix = (a * ax + b * bx + c * cx) / (a + b + c)\n    iy = (a * ay + b * by + c * cy) / (a + b + c)\n"
        "    return (ox - ix) ** 2 + (oy - iy) ** 2\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "euler_line_oh",
        "name": "Расстояние между центром описанной окружности и ортоцентром",
        "area": "геометрия",
        "when": "прямая Эйлера: OH = 3·OG, H — ортоцентр",
        "formula": "OH² = 9R² − (a² + b² + c²)",
        "code": "def solve(a, b, c):\n    p = (a + b + c) / 2\n    s = sqrt(p * (p - a) * (p - b) * (p - c))\n"
        "    R = a * b * c / (4 * s)\n    return 9 * R * R - (a * a + b * b + c * c)\n",
        "brute": "def solve(a, b, c):\n"
        + _COORDS
        + _CIRCUM
        + "    hx, hy = ax + bx + cx - 2 * ox, ay + by + cy - 2 * oy\n"
        "    return (ox - hx) ** 2 + (oy - hy) ** 2\n",
        "cases": [{"a": a, "b": b, "c": c} for a, b, c in _TRI],
    },
    {
        "id": "ptolemy",
        "name": "Теорема Птолемея",
        "area": "геометрия",
        "when": "вписанный четырёхугольник ABCD: произведение диагоналей; точки заданы углами на окружности",
        "formula": "AC·BD = AB·CD + AD·BC",
        "code": "def solve(r, t1, t2, t3, t4):\n"
        "    def ch(u, v):\n        return 2 * r * abs(sin(radians(v - u) / 2))\n"
        "    return ch(t1, t2) * ch(t3, t4) + ch(t1, t4) * ch(t2, t3)\n",
        "brute": "def solve(r, t1, t2, t3, t4):\n"
        "    def pt(t):\n        return (r * cos(radians(t)), r * sin(radians(t)))\n"
        "    A, B, C, D = pt(t1), pt(t2), pt(t3), pt(t4)\n"
        "    return hypot(A[0] - C[0], A[1] - C[1]) * hypot(B[0] - D[0], B[1] - D[1])\n",
        "cases": [
            {"r": r, "t1": 0, "t2": t2, "t3": t3, "t4": t4}
            for r in (1, 3)
            for t2, t3, t4 in ((40, 130, 250), (70, 160, 300), (20, 200, 330), (90, 180, 270))
        ],
    },
    {
        "id": "ceva",
        "name": "Теорема Чевы",
        "area": "геометрия",
        "when": "три чевианы пересекаются в одной точке; известны BD/DC и CE/EA — найти AF/FB",
        "formula": "(AF/FB)·(BD/DC)·(CE/EA) = 1",
        "code": "def solve(x, y):\n    return 1 / (x * y)\n",
        "brute": "def solve(x, y):\n"
        "    ax, ay, bx, by, cx, cy = 0.0, 0.0, 4.0, 0.0, 1.0, 3.0\n"
        "    dx, dy = (bx + x * cx) / (1 + x), (by + x * cy) / (1 + x)\n"
        "    ex, ey = (cx + y * ax) / (1 + y), (cy + y * ay) / (1 + y)\n"
        "    # пересечение AD и BE: A + s(D - A) = B + t(E - B)\n"
        "    m11, m12, m21, m22 = dx - ax, -(ex - bx), dy - ay, -(ey - by)\n"
        "    det = m11 * m22 - m12 * m21\n"
        "    s = ((bx - ax) * m22 - m12 * (by - ay)) / det\n"
        "    px, py = ax + s * (dx - ax), ay + s * (dy - ay)\n"
        "    # прямая CP пересекает AB (ось y = 0)\n"
        "    k = -cy / (py - cy)\n"
        "    fx = cx + k * (px - cx)\n"
        "    return (fx - ax) / (bx - fx)\n",
        "cases": [{"x": x, "y": y} for x in (0.5, 1, 2, 3) for y in (0.25, 1, 1.5, 4)],
    },
    {
        "id": "power_of_point",
        "name": "Степень точки",
        "area": "геометрия",
        "when": "прямая через точку P пересекает окружность в A и B: PA·PB не зависит от прямой",
        "formula": "PA·PB = |d² − R²|, d — расстояние от P до центра",
        "code": "def solve(R, d, ang):\n    return abs(d * d - R * R)\n",
        "brute": "def solve(R, d, ang):\n"
        "    ux, uy = cos(radians(ang)), sin(radians(ang))\n"
        "    # P = (d, 0); |P + t·u|² = R²  →  t² + 2d·ux·t + d² − R² = 0\n"
        "    bq, cq = 2 * d * ux, d * d - R * R\n"
        "    disc = sqrt(bq * bq - 4 * cq)\n"
        "    t1, t2 = (-bq + disc) / 2, (-bq - disc) / 2\n"
        "    return abs(t1) * abs(t2)\n",
        "cases": [{"R": 5, "d": d, "ang": a} for d in (1, 3, 7, 9) for a in (0, 10, 25)],
    },
    {
        "id": "chord_length",
        "name": "Длина хорды",
        "area": "геометрия",
        "when": "хорда на расстоянии d от центра окружности радиуса R",
        "formula": "2√(R² − d²)",
        "code": "def solve(R, d):\n    return 2 * sqrt(R * R - d * d)\n",
        "brute": "def solve(R, d):\n    y = sqrt(R * R - d * d)\n    return hypot(d - d, y - (-y))\n",
        "cases": [{"R": R, "d": d} for R in (5, 10, 13) for d in (0, 3, 4)],
    },
    {
        "id": "inscribed_angle",
        "name": "Теорема о вписанном угле",
        "area": "геометрия",
        "when": "вписанный угол равен половине центрального, опирающегося на ту же дугу",
        "formula": "∠ACB = ½·(дуга AB) — в градусах",
        "code": "def solve(arc, tc):\n    return arc / 2\n",
        "brute": "def solve(arc, tc):\n"
        "    A = (1.0, 0.0)\n    B = (cos(radians(arc)), sin(radians(arc)))\n"
        "    C = (cos(radians(tc)), sin(radians(tc)))\n"
        "    u, v = (A[0] - C[0], A[1] - C[1]), (B[0] - C[0], B[1] - C[1])\n"
        "    return degrees(acos((u[0] * v[0] + u[1] * v[1]) / (hypot(u[0], u[1]) * hypot(v[0], v[1]))))\n",
        "cases": [{"arc": a, "tc": t} for a in (40, 90, 120, 170) for t in (200, 250, 300)],
    },
    {
        "id": "shoelace",
        "name": "Площадь многоугольника по координатам (формула шнурования, Гаусс)",
        "area": "геометрия",
        "when": "вершины треугольника даны координатами",
        "formula": "S = ½·|Σ (x_i·y_{i+1} − x_{i+1}·y_i)|",
        "code": "def solve(x1, y1, x2, y2, x3, y3):\n"
        "    return abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2\n",
        "brute": "def solve(x1, y1, x2, y2, x3, y3):\n"
        "    a, b, c = hypot(x2 - x3, y2 - y3), hypot(x1 - x3, y1 - y3), hypot(x1 - x2, y1 - y2)\n"
        "    p = (a + b + c) / 2\n    return sqrt(max(p * (p - a) * (p - b) * (p - c), 0.0))\n",
        "cases": [
            {"x1": 0, "y1": 0, "x2": a, "y2": b, "x3": c, "y3": d}
            for a, b in ((4, 0), (5, 1), (3, 3))
            for c, d in ((0, 3), (2, 6), (-1, 4))
        ],
    },
    {
        "id": "regular_polygon_area",
        "name": "Площадь правильного n-угольника",
        "area": "геометрия",
        "when": "правильный многоугольник со стороной a",
        "formula": "S = n·a² / (4·tg(π/n))",
        "code": "def solve(n, a):\n    return n * a * a / (4 * tan(pi / n))\n",
        "brute": "def solve(n, a):\n    R = a / (2 * sin(pi / n))\n"
        "    pts = [(R * cos(2 * pi * k / n), R * sin(2 * pi * k / n)) for k in range(n)]\n"
        "    s = 0.0\n    for k in range(n):\n        x1, y1 = pts[k]\n        x2, y2 = pts[(k + 1) % n]\n"
        "        s += x1 * y2 - x2 * y1\n    return abs(s) / 2\n",
        "cases": [{"n": n, "a": a} for n in range(3, 13) for a in (1, 2)],
    },
    {
        "id": "polygon_angle_sum",
        "name": "Сумма углов выпуклого многоугольника",
        "area": "геометрия",
        "when": "сумма внутренних углов n-угольника (в градусах)",
        "formula": "180°·(n − 2)",
        "code": "def solve(n):\n    return 180 * (n - 2)\n",
        "brute": "def solve(n):\n    pts = [(cos(2*pi*k/n + 0.3*sin(k)), sin(2*pi*k/n + 0.3*sin(k))) for k in range(n)]\n"
        "    s = 0.0\n    for k in range(n):\n        px, py = pts[k - 1]\n        qx, qy = pts[k]\n"
        "        rx, ry = pts[(k + 1) % n]\n        u, v = (px - qx, py - qy), (rx - qx, ry - qy)\n"
        "        s += degrees(acos((u[0]*v[0] + u[1]*v[1]) / (hypot(u[0], u[1]) * hypot(v[0], v[1]))))\n"
        "    return s\n",
        "cases": [{"n": n} for n in range(3, 11)],
    },
    {
        "id": "point_line_distance",
        "name": "Расстояние от точки до прямой",
        "area": "геометрия",
        "when": "прямая ax + by + c = 0, точка (x0, y0)",
        "formula": "|a·x0 + b·y0 + c| / √(a² + b²)",
        "code": "def solve(a, b, c, x0, y0):\n    return abs(a * x0 + b * y0 + c) / sqrt(a * a + b * b)\n",
        "brute": "def solve(a, b, c, x0, y0):\n"
        "    # две точки прямой, площадь треугольника = ½·основание·высота\n"
        "    if b != 0:\n        p, q = (0.0, -c / b), (1.0, -(a + c) / b)\n"
        "    else:\n        p, q = (-c / a, 0.0), (-c / a, 1.0)\n"
        "    s2 = abs((q[0] - p[0]) * (y0 - p[1]) - (q[1] - p[1]) * (x0 - p[0]))\n"
        "    return s2 / hypot(q[0] - p[0], q[1] - p[1])\n",
        "cases": [
            {"a": a, "b": b, "c": c, "x0": x, "y0": y}
            for a, b, c in ((3, 4, -5), (1, 0, 2), (2, -1, 7))
            for x, y in ((0, 0), (5, 1), (-2, 3))
        ],
    },
    # ---------- Теория чисел ----------
    {
        "id": "wilson",
        "name": "Теорема Вильсона",
        "area": "теория чисел",
        "when": "остаток (p−1)! по простому модулю p; также признак простоты",
        "formula": "(p − 1)! ≡ −1 (mod p) для простого p",
        "code": "def solve(p):\n    return p - 1\n",
        "brute": "def solve(p):\n    f = 1\n    for k in range(1, p):\n        f = f * k % p\n    return f\n",
        "cases": [{"p": p} for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 101)],
    },
    {
        "id": "fermat_inverse",
        "name": "Обратный по простому модулю (малая теорема Ферма)",
        "area": "теория чисел",
        "when": "найти x: a·x ≡ 1 (mod p), p простое, a не делится на p",
        "formula": "a^(p−1) ≡ 1 (mod p)  ⇒  a⁻¹ ≡ a^(p−2) (mod p)",
        "code": "def solve(a, p):\n    return pow(a, p - 2, p)\n",
        "brute": "def solve(a, p):\n    for x in range(1, p):\n        if a * x % p == 1:\n            return x\n    return -1\n",
        "cases": [{"a": a, "p": p} for p in (5, 7, 13, 31, 97) for a in (2, 3, 4) if a % p],
    },
    {
        "id": "lte",
        "name": "Лемма о подъёме показателя (LTE)",
        "area": "теория чисел",
        "when": "степень нечётного простого p в a^n − b^n, если p | a − b и p ∤ a, b",
        "formula": "v_p(aⁿ − bⁿ) = v_p(a − b) + v_p(n)",
        "code": "def solve(a, b, n, p):\n"
        "    def v(x):\n        k = 0\n        for _ in range(64):\n            if x % p:\n                break\n"
        "            x //= p\n            k += 1\n        return k\n"
        "    return v(a - b) + v(n)\n",
        "brute": "def solve(a, b, n, p):\n    x = a**n - b**n\n    k = 0\n    for _ in range(200):\n"
        "        if x % p:\n            break\n        x //= p\n        k += 1\n    return k\n",
        "cases": [
            {"a": a, "b": b, "n": n, "p": p}
            for p, a, b in ((3, 4, 1), (3, 7, 4), (5, 6, 1), (5, 13, 3), (7, 9, 2))
            for n in (1, 2, 3, 5, 6, 9, 15, 25)
        ],
    },
    {
        "id": "frobenius_two",
        "name": "Задача о монетах Фробениуса (два номинала)",
        "area": "теория чисел",
        "when": "наибольшая сумма, которую нельзя набрать монетами a и b (НОД(a, b) = 1)",
        "formula": "ab − a − b; невыразимых сумм ровно (a−1)(b−1)/2",
        "code": "def solve(a, b):\n    return a * b - a - b\n",
        "brute": "def solve(a, b):\n    best = -1\n    for n in range(a * b + 1):\n"
        "        ok = any((n - a * x) % b == 0 for x in range(n // a + 1))\n"
        "        if not ok:\n            best = n\n    return best\n",
        "cases": [{"a": a, "b": b} for a, b in ((3, 5), (4, 7), (5, 8), (2, 9), (6, 11), (7, 10))],
    },
    {
        "id": "linear_diophantine_count",
        "name": "Число неотрицательных решений ax + by = n",
        "area": "теория чисел",
        "when": "линейное диофантово уравнение, НОД(a, b) = 1; решения идут с шагом x → x + b",
        "formula": "найти x0 ≡ n·a⁻¹ (mod b); ответ ⌊(n − a·x0)/(ab)⌋ + 1, если a·x0 ≤ n, иначе 0",
        "code": "def solve(a, b, n):\n    x0 = n * pow(a, -1, b) % b\n"
        "    if a * x0 > n:\n        return 0\n    return (n - a * x0) // (a * b) + 1\n",
        "brute": "def solve(a, b, n):\n    return sum(1 for x in range(n // a + 1) if (n - a * x) % b == 0)\n",
        "cases": [
            {"a": a, "b": b, "n": n} for a, b in ((3, 5), (4, 7), (2, 9)) for n in (0, 1, 7, 22, 40, 61)
        ],
    },
    {
        "id": "digit_root",
        "name": "Цифровой корень (признак делимости на 9)",
        "area": "теория чисел",
        "when": "многократно складывать цифры числа до одной цифры; число ≡ сумма цифр (mod 9)",
        "formula": "dr(n) = 1 + (n − 1) mod 9 при n > 0",
        "code": "def solve(n):\n    return 0 if n == 0 else 1 + (n - 1) % 9\n",
        "brute": "def solve(n):\n    for _ in range(10):\n        if n < 10:\n            return n\n"
        "        n = sum(int(ch) for ch in str(n))\n    return n\n",
        "cases": [{"n": n} for n in (0, 5, 9, 10, 99, 123, 2026, 987654321, 10**12 + 7)],
    },
    {
        "id": "factorial_digits",
        "name": "Количество цифр в n!",
        "area": "теория чисел",
        "when": "сколько цифр у большого факториала (или произведения) — через логарифм",
        "formula": "⌊Σ lg k⌋ + 1",
        "code": "def solve(n):\n    return floor(sum(log10(k) for k in range(1, n + 1))) + 1\n",
        "brute": "def solve(n):\n    return len(str(factorial(n)))\n",
        "cases": [{"n": n} for n in (1, 5, 10, 20, 50, 100, 200)],
    },
    {
        "id": "gauss_phi_sum",
        "name": "Тождество Гаусса для функции Эйлера",
        "area": "теория чисел",
        "when": "сумма φ(d) по всем делителям d числа n",
        "formula": "Σ_{d | n} φ(d) = n",
        "code": "def solve(n):\n    return n\n",
        "brute": "def solve(n):\n    return sum(sum(1 for k in range(1, d + 1) if gcd(k, d) == 1)"
        " for d in range(1, n + 1) if n % d == 0)\n",
        "cases": [{"n": n} for n in range(1, 40)],
    },
    {
        "id": "sum_gcd_k_n",
        "name": "Сумма НОД(k, n) по k = 1..n (функция Пиллаи)",
        "area": "теория чисел",
        "when": "Σ gcd(k, n) — группировка по значению НОД",
        "formula": "Σ_{d | n} d·φ(n/d)",
        "code": "def solve(n):\n"
        "    def phi(m):\n        return sum(1 for k in range(1, m + 1) if gcd(k, m) == 1)\n"
        "    return sum(d * phi(n // d) for d in range(1, n + 1) if n % d == 0)\n",
        "brute": "def solve(n):\n    return sum(gcd(k, n) for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(1, 40)],
    },
    # ---------- Алгебра и последовательности ----------
    {
        "id": "binet",
        "name": "Формула Бине для чисел Фибоначчи",
        "area": "последовательности",
        "when": "n-е число Фибоначчи (F1 = F2 = 1) без перебора; рост как φⁿ",
        "formula": "F_n = (φⁿ − ψⁿ)/√5, φ = (1+√5)/2, ψ = (1−√5)/2",
        "code": "def solve(n):\n    s5 = sqrt(5)\n    return round((((1 + s5) / 2) ** n - ((1 - s5) / 2) ** n) / s5)\n",
        "brute": "def solve(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n",
        "cases": [{"n": n} for n in range(0, 60)],
    },
    {
        "id": "vieta_sum_squares",
        "name": "Теорема Виета: сумма квадратов корней",
        "area": "алгебра",
        "when": "выражения от корней ax² + bx + c = 0 без нахождения корней: x1 + x2 = −b/a, x1·x2 = c/a",
        "formula": "x1² + x2² = (x1 + x2)² − 2x1x2 = (b² − 2ac)/a²",
        "code": "def solve(a, b, c):\n    return (b * b - 2 * a * c) / (a * a)\n",
        "brute": "def solve(a, b, c):\n    d = sqrt(b * b - 4 * a * c)\n"
        "    x1, x2 = (-b + d) / (2 * a), (-b - d) / (2 * a)\n    return x1 * x1 + x2 * x2\n",
        "cases": [
            {"a": a, "b": b, "c": c}
            for a in (1, 2, -3)
            for b in (5, -7, 9)
            for c in (1, -2, 3)
            if b * b > 4 * a * c
        ],
    },
    {
        "id": "am_gm_min",
        "name": "Неравенство о средних (AM ≥ GM): минимум x + k/x",
        "area": "алгебра",
        "when": "минимум суммы при фиксированном произведении; x > 0, k > 0",
        "formula": "x + k/x ≥ 2√k, равенство при x = √k",
        "code": "def solve(k):\n    return 2 * sqrt(k)\n",
        "brute": "def solve(k):\n    lo, hi = 1e-9, k + 1.0\n    for _ in range(300):\n"
        "        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3\n"
        "        if m1 + k / m1 < m2 + k / m2:\n            hi = m2\n        else:\n            lo = m1\n"
        "    x = (lo + hi) / 2\n    return x + k / x\n",
        "cases": [{"k": k} for k in (1, 2, 4, 9, 10, 50, 100)],
    },
    {
        "id": "infinite_geometric",
        "name": "Сумма бесконечно убывающей геометрической прогрессии",
        "area": "суммы",
        "when": "b + bq + bq² + … при |q| < 1",
        "formula": "S = b / (1 − q)",
        "code": "def solve(b, q):\n    return b / (1 - q)\n",
        "brute": "def solve(b, q):\n    s, t = 0.0, float(b)\n    for _ in range(3000):\n        s += t\n        t *= q\n    return s\n",
        "cases": [{"b": b, "q": q} for b in (1, 3, -2) for q in (0.5, -0.5, 0.25, 0.1, -0.3)],
    },
    {
        "id": "telescoping_triple",
        "name": "Телескопическая сумма 1/(k(k+1)(k+2))",
        "area": "суммы",
        "when": "1/(k(k+1)(k+2)) = ½·(1/(k(k+1)) − 1/((k+1)(k+2)))",
        "formula": "Σ_{k=1}^{n} = 1/4 − 1/(2(n+1)(n+2))",
        "code": "def solve(n):\n    return 0.25 - 1 / (2 * (n + 1) * (n + 2))\n",
        "brute": "def solve(n):\n    return sum(1 / (k * (k + 1) * (k + 2)) for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(1, 30)],
    },
    {
        "id": "sum_k_factorial",
        "name": "Сумма 1·1! + 2·2! + … + n·n!",
        "area": "суммы",
        "when": "k·k! = (k+1)! − k! — телескоп",
        "formula": "(n + 1)! − 1",
        "code": "def solve(n):\n    return factorial(n + 1) - 1\n",
        "brute": "def solve(n):\n    return sum(k * factorial(k) for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(0, 20)],
    },
    {
        "id": "vandermonde_squares",
        "name": "Сумма квадратов биномиальных коэффициентов (тождество Вандермонда)",
        "area": "комбинаторика",
        "when": "Σ C(n,k)² — выбор n из 2n по частям",
        "formula": "Σ_k C(n, k)² = C(2n, n)",
        "code": "def solve(n):\n    return comb(2 * n, n)\n",
        "brute": "def solve(n):\n    return sum(comb(n, k) ** 2 for k in range(n + 1))\n",
        "cases": [{"n": n} for n in range(0, 25)],
    },
    {
        "id": "hockey_stick",
        "name": "Тождество «хоккейная клюшка»",
        "area": "комбинаторика",
        "when": "сумма по столбцу треугольника Паскаля",
        "formula": "Σ_{i=r}^{n} C(i, r) = C(n + 1, r + 1)",
        "code": "def solve(n, r):\n    return comb(n + 1, r + 1)\n",
        "brute": "def solve(n, r):\n    return sum(comb(i, r) for i in range(r, n + 1))\n",
        "cases": [{"n": n, "r": r} for n in range(0, 16) for r in range(0, 5) if r <= n],
    },
    {
        "id": "sum_k_binom",
        "name": "Сумма k·C(n, k)",
        "area": "комбинаторика",
        "when": "выбрать команду и капитана: k·C(n,k) = n·C(n−1,k−1)",
        "formula": "Σ k·C(n, k) = n·2^(n−1)",
        "code": "def solve(n):\n    return n * 2 ** (n - 1) if n else 0\n",
        "brute": "def solve(n):\n    return sum(k * comb(n, k) for k in range(n + 1))\n",
        "cases": [{"n": n} for n in range(0, 25)],
    },
    # ---------- Комбинаторика ----------
    {
        "id": "pigeonhole_guarantee",
        "name": "Принцип Дирихле: сколько взять, чтобы точно было k одинаковых",
        "area": "комбинаторика",
        "when": "m видов предметов (ящиков); гарантировать k предметов одного вида",
        "formula": "m·(k − 1) + 1",
        "code": "def solve(m, k):\n    return m * (k - 1) + 1\n",
        "brute": "def solve(m, k):\n"
        "    # наибольшее число предметов без k одинаковых — перебором раскладок, затем +1\n"
        "    best = 0\n    for counts in product(range(k), repeat=m):\n        best = max(best, sum(counts))\n"
        "    return best + 1\n",
        "cases": [{"m": m, "k": k} for m in (1, 2, 3, 4) for k in (1, 2, 3, 4)],
    },
    {
        "id": "burnside_necklaces",
        "name": "Лемма Бёрнсайда: ожерелья из n бусин k цветов (с точностью до поворота)",
        "area": "комбинаторика",
        "when": "раскраски с точностью до поворотов; общий приём — среднее число неподвижных раскрасок",
        "formula": "(1/n)·Σ_{d | n} φ(d)·k^(n/d)",
        "code": "def solve(n, k):\n"
        "    def phi(m):\n        return sum(1 for j in range(1, m + 1) if gcd(j, m) == 1)\n"
        "    return sum(phi(d) * k ** (n // d) for d in range(1, n + 1) if n % d == 0) // n\n",
        "brute": "def solve(n, k):\n"
        "    reps = set(min(tuple(c[i:] + c[:i]) for i in range(n)) for c in product(range(k), repeat=n))\n"
        "    return len(reps)\n",
        "cases": [{"n": n, "k": k} for n in range(1, 8) for k in (1, 2, 3)],
    },
    {
        "id": "cayley_trees",
        "name": "Формула Кэли: число деревьев на n помеченных вершинах",
        "area": "графы",
        "when": "сколько разных деревьев (остовов полного графа) на n вершинах",
        "formula": "n^(n−2)",
        "code": "def solve(n):\n    return n ** (n - 2) if n >= 2 else 1\n",
        "brute": "def solve(n):\n    if n < 2:\n        return 1\n"
        "    edges = list(combinations(range(n), 2))\n    cnt = 0\n"
        "    for es in combinations(edges, n - 1):\n        comp = list(range(n))\n        ok = True\n"
        "        for u, v in es:\n            cu, cv = comp[u], comp[v]\n            if cu == cv:\n"
        "                ok = False\n                break\n"
        "            comp = [cu if x == cv else x for x in comp]\n"
        "        cnt += ok\n    return cnt\n",
        "cases": [{"n": n} for n in range(1, 7)],
    },
    {
        "id": "cycle_colorings",
        "name": "Раскраски цикла C_n в k цветов (хроматический многочлен)",
        "area": "графы",
        "when": "соседние вершины цикла (или сектора круга, места за круглым столом) разного цвета",
        "formula": "(k − 1)ⁿ + (−1)ⁿ·(k − 1)",
        "code": "def solve(n, k):\n    return (k - 1) ** n + (-1) ** n * (k - 1)\n",
        "brute": "def solve(n, k):\n    return sum(1 for c in product(range(k), repeat=n)"
        " if all(c[i] != c[(i + 1) % n] for i in range(n)))\n",
        "cases": [{"n": n, "k": k} for n in range(3, 8) for k in (2, 3, 4)],
    },
    {
        "id": "ballot",
        "name": "Задача о баллотировке",
        "area": "комбинаторика",
        "when": "A получил a голосов, B — b < a; сколько порядков подсчёта, где A всё время строго впереди",
        "formula": "(a − b)/(a + b)·C(a + b, a)",
        "code": "def solve(a, b):\n    return (a - b) * comb(a + b, a) // (a + b)\n",
        "brute": "def solve(a, b):\n    cnt = 0\n    for pos in combinations(range(a + b), b):\n"
        "        s, ok, ps = 0, True, set(pos)\n        for i in range(a + b):\n"
        "            s += -1 if i in ps else 1\n            if s <= 0:\n                ok = False\n                break\n"
        "        cnt += ok\n    return cnt\n",
        "cases": [{"a": a, "b": b} for a in range(1, 9) for b in range(0, a)],
    },
    {
        "id": "bell",
        "name": "Числа Белла: число разбиений множества",
        "area": "комбинаторика",
        "when": "сколькими способами разбить n различных предметов на непустые группы (порядок групп не важен)",
        "formula": "треугольник Белла: B(n+1) = Σ C(n, k)·B(k)",
        "code": "def solve(n):\n    B = [1]\n    for m in range(n):\n"
        "        B = B + [sum(comb(m, k) * B[k] for k in range(m + 1))]\n    return B[n]\n",
        "brute": "def solve(n):\n    # строки с ограниченным ростом: a0 = 0, a_i ≤ max(a_0..a_{i−1}) + 1\n"
        "    cnt = 0\n    for a in product(range(n), repeat=n):\n        ok, mx = True, -1\n"
        "        for x in a:\n            if x > mx + 1:\n                ok = False\n                break\n"
        "            mx = max(mx, x)\n        cnt += ok\n    return cnt if n else 1\n",
        "cases": [{"n": n} for n in range(0, 7)],
    },
    {
        "id": "no_adjacent_ones",
        "name": "Двоичные строки без двух единиц подряд",
        "area": "комбинаторика",
        "when": "рекуррента Фибоначчи: строки длины n без «11» (лестницы, рассадки без соседей)",
        "formula": "F(n + 2)",
        "code": "def solve(n):\n    a, b = 1, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return b\n",
        "brute": "def solve(n):\n    return sum(1 for s in product((0, 1), repeat=n)"
        " if all(not (s[i] and s[i + 1]) for i in range(n - 1)))\n",
        "cases": [{"n": n} for n in range(0, 15)],
    },
    {
        "id": "euler_odd_distinct",
        "name": "Теорема Эйлера о разбиениях: на различные = на нечётные части",
        "area": "комбинаторика",
        "when": "число разбиений n на различные слагаемые равно числу разбиений на нечётные слагаемые",
        "formula": "q(n) = число разбиений на нечётные части (считаем динамикой)",
        "code": "def solve(n):\n    dp = [1] + [0] * n\n    for part in range(1, n + 1, 2):\n"
        "        for s in range(part, n + 1):\n            dp[s] += dp[s - part]\n    return dp[n]\n",
        "brute": "def solve(n):\n    cnt = 0\n    for mask in product((0, 1), repeat=n):\n"
        "        if sum((i + 1) for i in range(n) if mask[i]) == n:\n            cnt += 1\n    return cnt\n",
        "cases": [{"n": n} for n in range(1, 17)],
    },
    {
        "id": "josephus2",
        "name": "Задача Иосифа Флавия (каждый второй)",
        "area": "комбинаторика",
        "when": "n человек по кругу, выбывает каждый второй — номер последнего",
        "formula": "J(n) = 2(n − 2^⌊log₂n⌋) + 1",
        "code": "def solve(n):\n    p = 1\n    for _ in range(64):\n        if p * 2 > n:\n            break\n"
        "        p *= 2\n    return 2 * (n - p) + 1\n",
        "brute": "def solve(n):\n    people = list(range(1, n + 1))\n    i = 0\n    for _ in range(n - 1):\n"
        "        i = (i + 1) % len(people)\n        people = people[:i] + people[i + 1:]\n"
        "        i = i % len(people)\n    return people[0]\n",
        "cases": [{"n": n} for n in range(1, 60)],
    },
    {
        "id": "hanoi",
        "name": "Ханойская башня",
        "area": "комбинаторика",
        "when": "наименьшее число перекладываний n дисков; рекуррента T(n) = 2T(n−1) + 1",
        "formula": "2ⁿ − 1",
        "code": "def solve(n):\n    return 2**n - 1\n",
        "brute": "def solve(n):\n    t = 0\n    for _ in range(n):\n        t = 2 * t + 1\n    return t\n",
        "cases": [{"n": n} for n in range(0, 30)],
    },
    {
        "id": "expected_geometric",
        "name": "Матожидание числа попыток до первого успеха",
        "area": "вероятность",
        "when": "повторяем опыт с вероятностью успеха p до первого успеха (кубик до шестёрки и т. п.)",
        "formula": "E = 1/p",
        "code": "def solve(p):\n    return 1 / p\n",
        "brute": "def solve(p):\n    return sum(k * (1 - p) ** (k - 1) * p for k in range(1, 4000))\n",
        "cases": [{"p": p} for p in (0.5, 1 / 6, 0.25, 0.1, 0.9)],
    },
    {
        "id": "wythoff",
        "name": "Игра Витхоффа: проигрышные позиции",
        "area": "игры",
        "when": "две кучки; берут из одной любое число или из обеих поровну. 1 — позиция (a, b) проигрышная",
        "formula": "a_k = ⌊kφ⌋, b_k = a_k + k, φ = (1+√5)/2",
        "code": "def solve(a, b):\n    a, b = min(a, b), max(a, b)\n    k = b - a\n"
        "    return 1 if a == floor(k * (1 + sqrt(5)) / 2) else 0\n",
        "brute": "def solve(a, b):\n    N = max(a, b) + 1\n    lose = [[False] * N for _ in range(N)]\n"
        "    for x in range(N):\n        for y in range(N):\n            win = False\n"
        "            for t in range(1, x + 1):\n                win = win or lose[x - t][y]\n"
        "            for t in range(1, y + 1):\n                win = win or lose[x][y - t]\n"
        "            for t in range(1, min(x, y) + 1):\n                win = win or lose[x - t][y - t]\n"
        "            lose[x][y] = not win\n    return 1 if lose[a][b] else 0\n",
        "cases": [{"a": a, "b": b} for a in range(0, 13) for b in range(a, 13, 3)],
    },
    # ---------- Физика ----------
    {
        "id": "projectile_range",
        "name": "Дальность полёта тела, брошенного под углом",
        "area": "физика",
        "when": "бросок с земли со скоростью v под углом α (в градусах), без сопротивления воздуха",
        "formula": "L = v²·sin 2α / g",
        "code": "def solve(v, alpha, g):\n    return v * v * sin(2 * radians(alpha)) / g\n",
        "brute": "def solve(v, alpha, g):\n    vx, vy = v * cos(radians(alpha)), v * sin(radians(alpha))\n"
        "    t = 2 * vy / g\n    return vx * t\n",
        "cases": [
            {"v": v, "alpha": a, "g": g} for v in (10, 20) for a in (15, 30, 45, 60, 75) for g in (9.8, 10)
        ],
    },
    {
        "id": "projectile_height",
        "name": "Наибольшая высота подъёма при броске под углом",
        "area": "физика",
        "when": "бросок со скоростью v под углом α (в градусах)",
        "formula": "H = v²·sin²α / (2g)",
        "code": "def solve(v, alpha, g):\n    return (v * sin(radians(alpha))) ** 2 / (2 * g)\n",
        "brute": "def solve(v, alpha, g):\n    vy = v * sin(radians(alpha))\n    lo, hi = 0.0, 2 * vy / g\n"
        "    for _ in range(300):\n        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3\n"
        "        if vy * m1 - g * m1 * m1 / 2 < vy * m2 - g * m2 * m2 / 2:\n            lo = m1\n"
        "        else:\n            hi = m2\n    t = (lo + hi) / 2\n    return vy * t - g * t * t / 2\n",
        "cases": [{"v": v, "alpha": a, "g": 10} for v in (10, 25) for a in (20, 45, 70, 90)],
    },
    {
        "id": "elastic_collision",
        "name": "Упругий центральный удар: скорость первого шара после удара",
        "area": "физика",
        "when": "законы сохранения импульса и энергии для двух шаров на прямой",
        "formula": "u1 = ((m1 − m2)v1 + 2m2·v2) / (m1 + m2)",
        "code": "def solve(m1, m2, v1, v2):\n    return ((m1 - m2) * v1 + 2 * m2 * v2) / (m1 + m2)\n",
        "brute": "def solve(m1, m2, v1, v2):\n"
        "    # из импульса u2 = (P − m1·u1)/m2, подставляем в энергию — квадратное уравнение на u1\n"
        "    P, E2 = m1 * v1 + m2 * v2, m1 * v1 * v1 + m2 * v2 * v2\n"
        "    A = m1 + m1 * m1 / m2\n    B = -2 * m1 * P / m2\n    C = P * P / m2 - E2\n"
        "    d = sqrt(max(B * B - 4 * A * C, 0.0))\n    r1, r2 = (-B + d) / (2 * A), (-B - d) / (2 * A)\n"
        "    return r2 if abs(r1 - v1) < 1e-9 else r1\n",
        "cases": [
            {"m1": a, "m2": b, "v1": v, "v2": w}
            for a, b in ((1, 2), (3, 1), (2, 5))
            for v, w in ((4, 0), (5, -2), (6, 1))
        ],
    },
    {
        "id": "orbital_period",
        "name": "Третий закон Кеплера (круговая орбита)",
        "area": "физика",
        "when": "период обращения спутника по круговой орбите радиуса r вокруг тела массы M",
        "formula": "T = 2π·√(r³ / (GM))",
        "code": "def solve(r, GM):\n    return 2 * pi * sqrt(r**3 / GM)\n",
        "brute": "def solve(r, GM):\n    v = sqrt(GM / r)  # mv²/r = GMm/r²\n    return 2 * pi * r / v\n",
        "cases": [{"r": r, "GM": gm} for r in (6.7e6, 4.2e7, 3.8e8) for gm in (3.986e14, 4.9e12)],
    },
    {
        "id": "free_fall_speed",
        "name": "Скорость после падения с высоты h (закон сохранения энергии)",
        "area": "физика",
        "when": "падение без начальной скорости и без сопротивления; соскальзывание без трения",
        "formula": "v = √(2gh)",
        "code": "def solve(h, g):\n    return sqrt(2 * g * h)\n",
        "brute": "def solve(h, g):\n    t = sqrt(2 * h / g)  # h = gt²/2\n    return g * t\n",
        "cases": [{"h": h, "g": g} for h in (1, 5, 20, 45, 100) for g in (9.8, 10)],
    },
    {
        "id": "thin_lens",
        "name": "Формула тонкой линзы",
        "area": "физика",
        "when": "расстояние до изображения b по расстоянию до предмета a и фокусу F (собирающая линза, a > F)",
        "formula": "1/a + 1/b = 1/F  ⇒  b = aF/(a − F); увеличение Γ = b/a",
        "code": "def solve(a, F):\n    return a * F / (a - F)\n",
        "brute": "def solve(a, F):\n"
        "    # ход лучей: луч через центр y = −h·x/a и луч, прошедший через фокус, y = h − h·x/F\n"
        "    h = 1.0\n    return h / (h / F - h / a)\n",
        "cases": [{"a": a, "F": f} for f in (5, 10, 12) for a in (15, 20, 30, 50)],
    },
    {
        "id": "parallel_resistors",
        "name": "Сопротивление параллельного соединения двух резисторов",
        "area": "физика",
        "when": "два резистора параллельно; при последовательном R = R1 + R2",
        "formula": "R = R1·R2 / (R1 + R2)",
        "code": "def solve(R1, R2):\n    return R1 * R2 / (R1 + R2)\n",
        "brute": "def solve(R1, R2):\n    U = 12.0\n    I = U / R1 + U / R2  # токи складываются, напряжение одно\n    return U / I\n",
        "cases": [{"R1": a, "R2": b} for a in (1, 2, 6, 10) for b in (3, 4, 12, 15)],
    },
]
