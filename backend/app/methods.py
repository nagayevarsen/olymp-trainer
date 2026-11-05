"""Банк методов и формул для проверки ответов в задачах с большими числами.

Полный перебор не проходит, когда в условии 2026 или 10^9. Тогда программа проверки:
1) решает маленькие случаи перебором,
2) сверяет их с формулой из этого банка,
3) только после совпадения считает ответ для большого числа.

Каждый метод — это код для песочницы (sandbox.py), а не текст. У каждого метода есть
честный перебор `brute` и набор маленьких случаев `cases`: тесты (tests/test_methods.py)
проверяют, что формула совпадает с перебором. Неверная формула в банк не попадёт.

Поля:
- id — имя функции, под которым метод виден программе проверки;
- name, area — название и раздел;
- when — когда применять (и когда НЕЛЬЗЯ);
- formula — формула словами для человека;
- code — функция solve(...) с формулой;
- brute — функция solve(...) с теми же аргументами, считает перебором по определению;
- cases — маленькие наборы аргументов для сверки.
"""

from __future__ import annotations

METHODS: list[dict] = [
    # ---------- Суммы ----------
    {
        "id": "gauss_sum",
        "name": "Сумма арифметической прогрессии (метод Гаусса)",
        "area": "суммы",
        "when": "сумма подряд идущих членов с постоянным шагом: 1+2+…+n, a+(a+d)+…",
        "formula": "S = (a1 + an)·n / 2, где an = a1 + (n−1)d",
        "code": "def solve(a, d, n):\n    return (2 * a + (n - 1) * d) * n // 2\n",
        "brute": "def solve(a, d, n):\n    return sum(a + i * d for i in range(n))\n",
        "cases": [{"a": a, "d": d, "n": n} for a in (1, 3, -2) for d in (1, 2, 5) for n in range(1, 12)],
    },
    {
        "id": "geom_sum",
        "name": "Сумма геометрической прогрессии",
        "area": "суммы",
        "when": "b + bq + bq² + … + bq^(n−1), q ≠ 1",
        "formula": "S = b·(q^n − 1)/(q − 1)",
        "code": "def solve(b, q, n):\n    return b * (q**n - 1) // (q - 1)\n",
        "brute": "def solve(b, q, n):\n    return sum(b * q**i for i in range(n))\n",
        "cases": [{"b": b, "q": q, "n": n} for b in (1, 3) for q in (2, 3, -2, 10) for n in range(1, 10)],
    },
    {
        "id": "sum_squares",
        "name": "Сумма квадратов 1² + … + n²",
        "area": "суммы",
        "when": "сумма квадратов подряд; также число квадратов любого размера в сетке n×n",
        "formula": "n(n+1)(2n+1)/6",
        "code": "def solve(n):\n    return n * (n + 1) * (2 * n + 1) // 6\n",
        "brute": "def solve(n):\n    return sum(k * k for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(0, 30)],
    },
    {
        "id": "sum_cubes",
        "name": "Сумма кубов 1³ + … + n³",
        "area": "суммы",
        "when": "сумма кубов подряд",
        "formula": "(n(n+1)/2)²",
        "code": "def solve(n):\n    return (n * (n + 1) // 2) ** 2\n",
        "brute": "def solve(n):\n    return sum(k**3 for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(0, 30)],
    },
    {
        "id": "telescoping_1_over_k_k1",
        "name": "Телескопическая сумма 1/(1·2) + 1/(2·3) + … + 1/(n(n+1))",
        "area": "суммы",
        "when": "дроби вида 1/(k(k+1)) раскладываются в 1/k − 1/(k+1), сумма «схлопывается»",
        "formula": "n/(n+1)",
        "code": "def solve(n):\n    return n / (n + 1)\n",
        "brute": "def solve(n):\n    return sum(1 / (k * (k + 1)) for k in range(1, n + 1))\n",
        "cases": [{"n": n} for n in range(1, 30)],
    },
    # ---------- Комбинаторика ----------
    {
        "id": "binom",
        "name": "Число сочетаний C(n, k)",
        "area": "комбинаторика",
        "when": "выбрать k предметов из n без учёта порядка",
        "formula": "n! / (k!(n−k)!)",
        "code": "def solve(n, k):\n    return comb(n, k)\n",
        "brute": "def solve(n, k):\n    return len([c for c in combinations(range(n), k)])\n",
        "cases": [{"n": n, "k": k} for n in range(0, 9) for k in range(0, n + 1)],
    },
    {
        "id": "arrangements",
        "name": "Размещения A(n, k)",
        "area": "комбинаторика",
        "when": "выбрать k предметов из n с учётом порядка (призовые места, коды без повторов)",
        "formula": "n! / (n−k)!",
        "code": "def solve(n, k):\n    return perm(n, k)\n",
        "brute": "def solve(n, k):\n    return len([p for p in permutations(range(n), k)])\n",
        "cases": [{"n": n, "k": k} for n in range(0, 7) for k in range(0, n + 1)],
    },
    {
        "id": "multiset_permutations",
        "name": "Перестановки с повторениями (мультиномиальный коэффициент)",
        "area": "комбинаторика",
        "when": "сколько различных слов из букв, где буквы повторяются: МАТЕМАТИКА и т. п.",
        "formula": "n! / (n1!·n2!·…·nk!)",
        "code": (
            "def solve(a, b, c):\n"
            "    return factorial(a + b + c) // (factorial(a) * factorial(b) * factorial(c))\n"
        ),
        "brute": (
            "def solve(a, b, c):\n"
            "    word = [0] * a + [1] * b + [2] * c\n"
            "    return len(set(p for p in permutations(word)))\n"
        ),
        "cases": [{"a": a, "b": b, "c": c} for a in range(0, 4) for b in range(0, 3) for c in range(0, 3)],
    },
    {
        "id": "stars_and_bars",
        "name": "Звёзды и перегородки (сочетания с повторениями)",
        "area": "комбинаторика",
        "when": "разложить n одинаковых предметов по k ящикам (ящики могут быть пустыми); "
        "число решений x1+…+xk = n в целых неотрицательных",
        "formula": "C(n + k − 1, k − 1)",
        "code": "def solve(n, k):\n    return comb(n + k - 1, k - 1)\n",
        "brute": (
            "def solve(n, k):\n    return len([t for t in product(range(n + 1), repeat=k) if sum(t) == n])\n"
        ),
        "cases": [{"n": n, "k": k} for n in range(0, 7) for k in range(1, 5)],
    },
    {
        "id": "compositions_positive",
        "name": "Решения x1+…+xk = n в натуральных числах",
        "area": "комбинаторика",
        "when": "разбить n на k положительных слагаемых, порядок важен",
        "formula": "C(n − 1, k − 1)",
        "code": "def solve(n, k):\n    return comb(n - 1, k - 1)\n",
        "brute": (
            "def solve(n, k):\n"
            "    return len([t for t in product(range(1, n + 1), repeat=k) if sum(t) == n])\n"
        ),
        "cases": [{"n": n, "k": k} for n in range(1, 8) for k in range(1, 5)],
    },
    {
        "id": "grid_paths",
        "name": "Пути по клетчатой сетке (только вправо и вверх)",
        "area": "комбинаторика",
        "when": "число кратчайших путей из угла прямоугольника m×n в противоположный",
        "formula": "C(m + n, n)",
        "code": "def solve(m, n):\n    return comb(m + n, n)\n",
        "brute": (
            "def solve(m, n):\n    return len([s for s in product((0, 1), repeat=m + n) if sum(s) == n])\n"
        ),
        "cases": [{"m": m, "n": n} for m in range(0, 6) for n in range(0, 6)],
    },
    {
        "id": "derangements",
        "name": "Беспорядки (никто не получил свой предмет)",
        "area": "комбинаторика",
        "when": "перестановки без неподвижных точек: письма не в свои конверты, шляпы",
        "formula": "!n = (n − 1)(!(n−1) + !(n−2)), !0 = 1, !1 = 0",
        "code": (
            "def solve(n):\n"
            "    a, b = 1, 0\n"
            "    if n == 0:\n"
            "        return 1\n"
            "    for k in range(2, n + 1):\n"
            "        a, b = b, (k - 1) * (a + b)\n"
            "    return b\n"
        ),
        "brute": (
            "def solve(n):\n"
            "    return len([p for p in permutations(range(n)) if all(p[i] != i for i in range(n))])\n"
        ),
        "cases": [{"n": n} for n in range(0, 8)],
    },
    {
        "id": "catalan",
        "name": "Числа Каталана",
        "area": "комбинаторика",
        "when": "правильные скобочные последовательности из n пар, пути Дика, триангуляции (n+2)-угольника",
        "formula": "C(2n, n) / (n + 1)",
        "code": "def solve(n):\n    return comb(2 * n, n) // (n + 1)\n",
        "brute": (
            "def solve(n):\n"
            "    c = 0\n"
            "    for s in product((1, -1), repeat=2 * n):\n"
            "        h = 0\n"
            "        ok = True\n"
            "        for x in s:\n"
            "            h += x\n"
            "            if h < 0:\n"
            "                ok = False\n"
            "                break\n"
            "        if ok and h == 0:\n"
            "            c += 1\n"
            "    return c\n"
        ),
        "cases": [{"n": n} for n in range(0, 8)],
    },
    {
        "id": "fibonacci_stairs",
        "name": "Числа Фибоначчи (лестница шагами 1 и 2)",
        "area": "комбинаторика",
        "when": "подняться на n ступенек шагами 1 и 2; замостить полосу 2×n доминошками; "
        "двоичные строки длины n−1 без двух единиц подряд",
        "formula": "F(n) = F(n−1) + F(n−2), F(0) = F(1) = 1",
        "code": (
            "def solve(n):\n"
            "    a, b = 1, 1\n"
            "    for i in range(n - 1):\n"
            "        a, b = b, a + b\n"
            "    return b if n >= 1 else 1\n"
        ),
        "brute": (
            "def solve(n):\n"
            "    c = 0\n"
            "    for k in range(n + 1):\n"
            "        for s in product((1, 2), repeat=k):\n"
            "            if sum(s) == n:\n"
            "                c += 1\n"
            "    return c\n"
        ),
        "cases": [{"n": n} for n in range(0, 12)],
    },
    {
        "id": "surjections",
        "name": "Сюръекции (все ящики непустые)",
        "area": "комбинаторика",
        "when": "разложить n различных предметов по k различным ящикам так, чтобы ни один не был пуст",
        "formula": "Σ (−1)^i C(k, i)(k − i)^n по i = 0…k (включения-исключения)",
        "code": "def solve(n, k):\n    return sum((-1) ** i * comb(k, i) * (k - i) ** n for i in range(k + 1))\n",
        "brute": (
            "def solve(n, k):\n    return len([f for f in product(range(k), repeat=n) if len(set(f)) == k])\n"
        ),
        "cases": [{"n": n, "k": k} for n in range(0, 7) for k in range(1, 5)],
    },
    {
        "id": "partitions",
        "name": "Разбиения числа на слагаемые (порядок не важен)",
        "area": "комбинаторика",
        "when": "сколькими способами записать n как сумму натуральных слагаемых без учёта порядка",
        "formula": "динамика: p[s] += p[s − k] для k = 1…n",
        "code": (
            "def solve(n):\n"
            "    p = [1] + [0] * n\n"
            "    for k in range(1, n + 1):\n"
            "        for s in range(k, n + 1):\n"
            "            p[s] += p[s - k]\n"
            "    return p[n]\n"
        ),
        "brute": (
            "def solve(n):\n"
            "    def count(rest, mx):\n"
            "        if rest == 0:\n"
            "            return 1\n"
            "        return sum(count(rest - k, k) for k in range(1, min(rest, mx) + 1))\n"
            "    return count(n, n)\n"
        ),
        "cases": [{"n": n} for n in range(0, 16)],
    },
    {
        "id": "inclusion_exclusion_div",
        "name": "Включения-исключения: числа до N, делящиеся на a или на b",
        "area": "комбинаторика",
        "when": "сколько чисел от 1 до N делятся хотя бы на одно из a, b (или ни на одно — вычесть из N)",
        "formula": "⌊N/a⌋ + ⌊N/b⌋ − ⌊N/НОК(a,b)⌋",
        "code": "def solve(N, a, b):\n    return N // a + N // b - N // lcm(a, b)\n",
        "brute": "def solve(N, a, b):\n    return len([x for x in range(1, N + 1) if x % a == 0 or x % b == 0])\n",
        "cases": [{"N": N, "a": a, "b": b} for N in (1, 10, 37, 100) for a in (2, 3, 4) for b in (3, 5, 6)],
    },
    {
        "id": "pigeonhole_min",
        "name": "Принцип Дирихле: сколько взять, чтобы гарантированно",
        "area": "комбинаторика",
        "when": "минимальное число предметов, чтобы при любом раскладе по m ящикам (цветам) "
        "в каком-то оказалось не меньше k. Только для такой постановки!",
        "formula": "(k − 1)·m + 1",
        "code": "def solve(m, k):\n    return (k - 1) * m + 1\n",
        "brute": (
            "def solve(m, k):\n"
            "    for N in range(1, m * k + 2):\n"
            "        if all(max(t) >= k for t in product(range(N + 1), repeat=m) if sum(t) == N):\n"
            "            return N\n"
            "    return -1\n"
        ),
        "cases": [{"m": m, "k": k} for m in range(1, 4) for k in range(1, 5)],
    },
    # ---------- Теория чисел ----------
    {
        "id": "count_multiples",
        "name": "Количество чисел от 1 до N, кратных d",
        "area": "теория чисел",
        "when": "сколько кратных d на отрезке [1, N]; на отрезке [A, B] — ⌊B/d⌋ − ⌊(A−1)/d⌋",
        "formula": "⌊N/d⌋",
        "code": "def solve(N, d):\n    return N // d\n",
        "brute": "def solve(N, d):\n    return len([x for x in range(1, N + 1) if x % d == 0])\n",
        "cases": [{"N": N, "d": d} for N in range(0, 40, 3) for d in range(1, 8)],
    },
    {
        "id": "num_divisors",
        "name": "Число делителей τ(n)",
        "area": "теория чисел",
        "when": "сколько натуральных делителей у числа; если n = p1^a1·…·pk^ak, то τ = (a1+1)…(ak+1)",
        "formula": "произведение (показатель + 1) по разложению на простые",
        "code": (
            "def solve(n):\n"
            "    t = 1\n"
            "    p = 2\n"
            "    for p in range(2, isqrt(n) + 2):\n"
            "        a = 0\n"
            "        for i in range(64):\n"
            "            if n % p != 0:\n"
            "                break\n"
            "            n //= p\n"
            "            a += 1\n"
            "        t *= a + 1\n"
            "    return t * (2 if n > 1 else 1)\n"
        ),
        "brute": "def solve(n):\n    return len([d for d in range(1, n + 1) if n % d == 0])\n",
        "cases": [{"n": n} for n in range(1, 200)],
    },
    {
        "id": "sum_divisors",
        "name": "Сумма делителей σ(n)",
        "area": "теория чисел",
        "when": "сумма всех натуральных делителей; совершенные числа (σ(n) = 2n)",
        "formula": "произведение (p^(a+1) − 1)/(p − 1) по разложению",
        "code": (
            "def solve(n):\n"
            "    s = 1\n"
            "    for p in range(2, isqrt(n) + 2):\n"
            "        pk = 1\n"
            "        part = 1\n"
            "        for i in range(64):\n"
            "            if n % p != 0:\n"
            "                break\n"
            "            n //= p\n"
            "            pk *= p\n"
            "            part += pk\n"
            "        s *= part\n"
            "    return s * (n + 1 if n > 1 else 1)\n"
        ),
        "brute": "def solve(n):\n    return sum(d for d in range(1, n + 1) if n % d == 0)\n",
        "cases": [{"n": n} for n in range(1, 200)],
    },
    {
        "id": "euler_phi",
        "name": "Функция Эйлера φ(n)",
        "area": "теория чисел",
        "when": "сколько чисел от 1 до n взаимно просты с n; несократимые дроби со знаменателем n",
        "formula": "n·Π(1 − 1/p) по простым делителям p",
        "code": (
            "def solve(n):\n"
            "    r = n\n"
            "    for p in range(2, isqrt(n) + 2):\n"
            "        if n % p == 0:\n"
            "            r = r // p * (p - 1)\n"
            "            for i in range(64):\n"
            "                if n % p != 0:\n"
            "                    break\n"
            "                n //= p\n"
            "    if n > 1:\n"
            "        r = r // n * (n - 1)\n"
            "    return r\n"
        ),
        "brute": "def solve(n):\n    return len([k for k in range(1, n + 1) if gcd(k, n) == 1])\n",
        "cases": [{"n": n} for n in range(1, 200)],
    },
    {
        "id": "pow_mod",
        "name": "Остаток степени (быстрое возведение по модулю, малая теорема Ферма)",
        "area": "теория чисел",
        "when": "остаток a^b при делении на m при огромном b; последние цифры степени",
        "formula": "pow(a, b, m); для простого p и a не кратного p: a^(p−1) ≡ 1 (mod p)",
        "code": "def solve(a, b, m):\n    return pow(a, b, m)\n",
        "brute": "def solve(a, b, m):\n    return a**b % m\n",
        "cases": [
            {"a": a, "b": b, "m": m} for a in (2, 3, 7, 10) for b in range(0, 25, 4) for m in (5, 7, 10, 13)
        ],
    },
    {
        "id": "last_digit_cycle",
        "name": "Последняя цифра степени через период",
        "area": "теория чисел",
        "when": "последняя цифра a^n: последние цифры степеней повторяются с периодом 1, 2 или 4",
        "formula": "последняя цифра a^n = последняя цифра a^(1 + (n − 1) mod 4) при n ≥ 1",
        "code": "def solve(a, n):\n    return pow(a % 10, 1 + (n - 1) % 4, 10) if n >= 1 else 1\n",
        "brute": "def solve(a, n):\n    return a**n % 10\n",
        "cases": [{"a": a, "n": n} for a in range(0, 13) for n in range(0, 20)],
    },
    {
        "id": "legendre",
        "name": "Формула Лежандра: степень простого p в n!",
        "area": "теория чисел",
        "when": "на какую наибольшую степень p делится n!; количество нулей в конце n! (p = 5)",
        "formula": "⌊n/p⌋ + ⌊n/p²⌋ + ⌊n/p³⌋ + …",
        "code": (
            "def solve(n, p):\n"
            "    s = 0\n"
            "    q = p\n"
            "    for i in range(64):\n"
            "        if q > n:\n"
            "            break\n"
            "        s += n // q\n"
            "        q *= p\n"
            "    return s\n"
        ),
        "brute": (
            "def solve(n, p):\n"
            "    f = factorial(n)\n"
            "    s = 0\n"
            "    for i in range(200):\n"
            "        if f % p != 0:\n"
            "            break\n"
            "        f //= p\n"
            "        s += 1\n"
            "    return s\n"
        ),
        "cases": [{"n": n, "p": p} for n in range(0, 60, 3) for p in (2, 3, 5, 7)],
    },
    {
        "id": "crt_two",
        "name": "Китайская теорема об остатках (два модуля)",
        "area": "теория чисел",
        "when": "наименьшее натуральное x: x ≡ a (mod m), x ≡ b (mod n), где НОД(m, n) = 1",
        "formula": "x единственно по модулю m·n; ищется перебором x = a, a + m, a + 2m, … (не больше n шагов)",
        "code": (
            "def solve(a, m, b, n):\n"
            "    for t in range(n):\n"
            "        x = a % m + t * m\n"
            "        if x % n == b % n:\n"
            "            return x if x > 0 else m * n\n"
            "    return -1\n"
        ),
        "brute": (
            "def solve(a, m, b, n):\n"
            "    for x in range(1, m * n + 1):\n"
            "        if x % m == a % m and x % n == b % n:\n"
            "            return x\n"
            "    return -1\n"
        ),
        "cases": [
            {"a": a, "m": m, "b": b, "n": n}
            for a in range(0, 4)
            for b in range(0, 5)
            for m, n in ((3, 5), (4, 7), (5, 6))
        ],
    },
    {
        "id": "digit_sum_count",
        "name": "Сколько чисел от 0 до 10^k − 1 имеют сумму цифр s (динамика по цифрам)",
        "area": "теория чисел",
        "when": "подсчёт чисел с условием на цифры, когда чисел слишком много для перебора",
        "formula": "dp[i][t] — сколько i-значных строк цифр с суммой t; dp[i+1][t+c] += dp[i][t]",
        "code": (
            "def solve(k, s):\n"
            "    dp = [1] + [0] * s\n"
            "    for i in range(k):\n"
            "        dp = [sum(dp[t - c] for c in range(10) if t - c >= 0) for t in range(s + 1)]\n"
            "    return dp[s]\n"
        ),
        "brute": (
            "def solve(k, s):\n"
            "    return len([x for x in range(10**k) if sum(int(c) for c in str(x)) == s])\n"
        ),
        "cases": [{"k": k, "s": s} for k in range(1, 5) for s in range(0, 20, 2)],
    },
    {
        "id": "binary_ones",
        "name": "Число единиц в двоичной записи",
        "area": "теория чисел",
        "when": "двоичная запись, степени двойки, игры с удвоением; число нечётных C(n, k) = 2^(единиц в n)",
        "formula": "считаем единицы через деление на 2",
        "code": (
            "def solve(n):\n"
            "    c = 0\n"
            "    for i in range(200):\n"
            "        if n == 0:\n"
            "            break\n"
            "        c += n % 2\n"
            "        n //= 2\n"
            "    return 2**c\n"
        ),
        "brute": "def solve(n):\n    return len([k for k in range(n + 1) if comb(n, k) % 2 == 1])\n",
        "cases": [{"n": n} for n in range(0, 70)],
    },
    {
        "id": "period_of_sequence",
        "name": "Период последовательности остатков",
        "area": "теория чисел",
        "when": "a(n) задаётся рекуррентно по модулю m (например Фибоначчи mod m) и нужно a(10^9): "
        "найти период и взять номер по модулю периода",
        "formula": "последовательность пар (a(n), a(n+1)) mod m повторяется; период Пизано",
        "code": (
            "def solve(N, m):\n"
            "    a, b = 0, 1\n"
            "    period = 0\n"
            "    for i in range(1, 6 * m * m + 1):\n"
            "        a, b = b, (a + b) % m\n"
            "        if a == 0 and b == 1:\n"
            "            period = i\n"
            "            break\n"
            "    a, b = 0, 1\n"
            "    for i in range(N % period):\n"
            "        a, b = b, (a + b) % m\n"
            "    return a\n"
        ),
        "brute": (
            "def solve(N, m):\n"
            "    a, b = 0, 1\n"
            "    for i in range(N):\n"
            "        a, b = b, a + b\n"
            "    return a % m\n"
        ),
        "cases": [{"N": N, "m": m} for N in range(0, 60, 7) for m in (2, 3, 7, 10)],
    },
    # ---------- Графы и игры ----------
    {
        "id": "complete_graph_edges",
        "name": "Рёбра полного графа (рукопожатия, матчи в круговом турнире)",
        "area": "графы",
        "when": "каждый с каждым по одному разу: рукопожатия, партии в круговом турнире, отрезки между точками",
        "formula": "n(n − 1)/2",
        "code": "def solve(n):\n    return n * (n - 1) // 2\n",
        "brute": "def solve(n):\n    return len([e for e in combinations(range(n), 2)])\n",
        "cases": [{"n": n} for n in range(0, 15)],
    },
    {
        "id": "polygon_diagonals",
        "name": "Число диагоналей n-угольника",
        "area": "графы",
        "when": "диагонали выпуклого многоугольника",
        "formula": "n(n − 3)/2",
        "code": "def solve(n):\n    return n * (n - 3) // 2\n",
        "brute": (
            "def solve(n):\n"
            "    return len([e for e in combinations(range(n), 2) if (e[1] - e[0]) % n not in (1, n - 1)])\n"
        ),
        "cases": [{"n": n} for n in range(3, 15)],
    },
    {
        "id": "tree_edges",
        "name": "Дерево: рёбер на одно меньше, чем вершин",
        "area": "графы",
        "when": "связный граф без циклов: дороги без кругов, турнир на выбывание (матчей = участников − 1)",
        "formula": "E = V − 1; число помеченных деревьев на n вершинах — n^(n−2) (формула Кэли)",
        "code": "def solve(n):\n    return n ** (n - 2) if n >= 2 else 1\n",
        "brute": (
            "def solve(n):\n"
            "    if n < 2:\n"
            "        return 1\n"
            "    edges = [e for e in combinations(range(n), 2)]\n"
            "    c = 0\n"
            "    for es in combinations(edges, n - 1):\n"
            "        comp = list(range(n))\n"
            "        ok = True\n"
            "        for u, v in es:\n"
            "            cu, cv = comp[u], comp[v]\n"
            "            if cu == cv:\n"
            "                ok = False\n"
            "                break\n"
            "            comp = [cu if x == cv else x for x in comp]\n"
            "        if ok:\n"
            "            c += 1\n"
            "    return c\n"
        ),
        "cases": [{"n": n} for n in range(1, 7)],
    },
    {
        "id": "euler_planar",
        "name": "Формула Эйлера для плоских графов",
        "area": "графы",
        "when": "связный плоский граф (карта, разрезание фигуры): V − E + F = 2, где F считает и внешнюю грань",
        "formula": "F = E − V + 2",
        "code": "def solve(V, E):\n    return E - V + 2\n",
        "brute": (
            "def solve(V, E):\n"
            "    # проверка на семействе «колесо»: центр + цикл из V − 1 вершин, E = 2(V − 1),\n"
            "    # граней: V − 1 треугольник + внешняя\n"
            "    return (V - 1) + 1 if E == 2 * (V - 1) else -1\n"
        ),
        "cases": [{"V": V, "E": 2 * (V - 1)} for V in range(4, 15)],
    },
    {
        "id": "lines_regions",
        "name": "Части плоскости, на которые делят n прямых общего положения",
        "area": "графы",
        "when": "никакие две прямые не параллельны и никакие три не проходят через одну точку",
        "formula": "n(n + 1)/2 + 1",
        "code": "def solve(n):\n    return n * (n + 1) // 2 + 1\n",
        "brute": "def solve(n):\n    r = 1\n    for k in range(1, n + 1):\n        r += k\n    return r\n",
        "cases": [{"n": n} for n in range(0, 20)],
    },
    {
        "id": "nim",
        "name": "Ним: кто выигрывает",
        "area": "игры",
        "when": "несколько кучек, за ход можно взять любое число камней из одной кучки, "
        "взявший последний выигрывает. Возвращает 1, если выигрывает первый",
        "formula": "первый выигрывает ⇔ a1 xor a2 xor … ≠ 0",
        "code": "def solve(a, b, c):\n    return 1 if (a ^ b ^ c) != 0 else 0\n",
        "brute": (
            "def solve(a, b, c):\n"
            "    def win(x, y, z):\n"
            "        for nx in range(x):\n"
            "            if not win(nx, y, z):\n"
            "                return True\n"
            "        for ny in range(y):\n"
            "            if not win(x, ny, z):\n"
            "                return True\n"
            "        for nz in range(z):\n"
            "            if not win(x, y, nz):\n"
            "                return True\n"
            "        return False\n"
            "    return 1 if win(a, b, c) else 0\n"
        ),
        "cases": [{"a": a, "b": b, "c": c} for a in range(0, 4) for b in range(0, 4) for c in range(0, 4)],
    },
    {
        "id": "subtraction_game",
        "name": "Игра «бери от 1 до k камней»",
        "area": "игры",
        "when": "одна кучка из n камней, за ход берут от 1 до k, взявший последний выигрывает. "
        "Возвращает 1, если выигрывает первый",
        "formula": "проигрышные позиции — n кратно (k + 1)",
        "code": "def solve(n, k):\n    return 0 if n % (k + 1) == 0 else 1\n",
        "brute": (
            "def solve(n, k):\n"
            "    win = [False] * (n + 1)\n"
            "    for m in range(1, n + 1):\n"
            "        win[m] = any(not win[m - t] for t in range(1, min(k, m) + 1))\n"
            "    return 1 if win[n] else 0\n"
        ),
        "cases": [{"n": n, "k": k} for n in range(0, 25) for k in range(1, 5)],
    },
    # ---------- Геометрия на решётке ----------
    {
        "id": "pick",
        "name": "Формула Пика",
        "area": "геометрия",
        "when": "площадь многоугольника с вершинами в узлах сетки: I — узлы внутри, B — на границе",
        "formula": "S = I + B/2 − 1",
        "code": "def solve(I, B):\n    return I + B / 2 - 1\n",
        "brute": (
            "def solve(I, B):\n"
            "    # прямоугольник a×b: B = 2(a+b), I = (a−1)(b−1), площадь a·b — ищем такой прямоугольник\n"
            "    for a in range(1, 30):\n"
            "        for b in range(1, 30):\n"
            "            if 2 * (a + b) == B and (a - 1) * (b - 1) == I:\n"
            "                return a * b\n"
            "    return -1\n"
        ),
        "cases": [{"I": (a - 1) * (b - 1), "B": 2 * (a + b)} for a in range(1, 8) for b in range(a, 8)],
    },
    {
        "id": "rectangles_in_grid",
        "name": "Число прямоугольников в сетке m×n",
        "area": "геометрия",
        "when": "сколько прямоугольников (любого размера) по линиям клетчатого прямоугольника m×n",
        "formula": "C(m + 1, 2)·C(n + 1, 2)",
        "code": "def solve(m, n):\n    return comb(m + 1, 2) * comb(n + 1, 2)\n",
        "brute": (
            "def solve(m, n):\n"
            "    return len([1 for x in combinations(range(m + 1), 2) for y in combinations(range(n + 1), 2)])\n"
        ),
        "cases": [{"m": m, "n": n} for m in range(1, 7) for n in range(1, 7)],
    },
    {
        "id": "lattice_points_on_segment",
        "name": "Узлы сетки на отрезке",
        "area": "геометрия",
        "when": "сколько точек с целыми координатами лежит на отрезке от (0, 0) до (a, b), включая концы",
        "formula": "НОД(a, b) + 1",
        "code": "def solve(a, b):\n    return gcd(a, b) + 1\n",
        "brute": (
            "def solve(a, b):\n"
            "    return len([1 for x in range(a + 1) for y in range(b + 1) if x * b == y * a])\n"
        ),
        "cases": [{"a": a, "b": b} for a in range(1, 13) for b in range(1, 13)],
    },
    {
        "id": "heron",
        "name": "Формула Герона",
        "area": "геометрия",
        "when": "площадь треугольника по трём сторонам",
        "formula": "S = √(p(p − a)(p − b)(p − c)), p — полупериметр",
        "code": (
            "def solve(a, b, c):\n    p = (a + b + c) / 2\n    return sqrt(p * (p - a) * (p - b) * (p - c))\n"
        ),
        "brute": (
            "def solve(a, b, c):\n"
            "    # через координаты: A(0,0), B(c,0), C(x,y)\n"
            "    x = (b * b + c * c - a * a) / (2 * c)\n"
            "    y = sqrt(b * b - x * x)\n"
            "    return c * y / 2\n"
        ),
        "cases": [
            {"a": a, "b": b, "c": c}
            for a in range(2, 9)
            for b in range(2, 9)
            for c in range(2, 9)
            if a + b > c and a + c > b and b + c > a
        ],
    },
]


def methods_by_id() -> dict[str, dict]:
    return {m["id"]: m for m in METHODS}


def helper_code(method: dict) -> str:
    """Код метода как вспомогательной функции с именем id (для вставки в программу проверки)."""
    return method["code"].replace("def solve(", f"def {method['id']}(", 1)


def catalog_text() -> str:
    """Короткий каталог для подсказки модели: имя функции, когда применять, формула."""
    lines = []
    for m in METHODS:
        args = m["code"].split("(", 1)[1].split(")", 1)[0]
        lines.append(f"- {m['id']}({args}) — {m['name']}. Когда: {m['when']}. Формула: {m['formula']}")
    return "\n".join(lines)
