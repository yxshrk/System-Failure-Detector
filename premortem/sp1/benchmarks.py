"""SP1 benchmark functions.

Tasks are adapted from HumanEval/EvalPlus-style problems plus a few
business-rule functions. Following the contamination mitigation in the
proposal, identifiers are renamed and every docstring is rewritten from
scratch; docstrings carry no worked examples, so a bug cannot be spotted by
checking an example by eye. Each docstring is the *specification*: it must
determine the return value for every input in the stated domain, and the
reference body implements exactly that.

A benchmark is assembled as ``helpers + def line + docstring + body``.
Hand-written mutants are textual replacements applied to that source.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field

from .domain import BoolT, IntT, ListT, Type


@dataclass
class Benchmark:
    name: str
    params: list[tuple[str, Type]]
    doc: str
    body: str
    loop_bound: int = 8
    helpers: str = ""
    hand: list[tuple[str, str, str]] = field(default_factory=list)  # (description, old, new): bugs
    rewrites: list[tuple[str, str, str]] = field(default_factory=list)  # equivalent rewrites (controls)
    origin: str = ""
    tier: str = "base"

    @property
    def signature(self) -> str:
        return f"def {self.name}({', '.join(p for p, _ in self.params)}):"

    def assemble(self, body: str | None = None, helpers: str | None = None) -> str:
        doc = textwrap.indent('"""' + textwrap.dedent(self.doc).strip() + '\n"""', "    ")
        code = textwrap.indent(textwrap.dedent(body if body is not None else self.body).strip(), "    ")
        helpers = textwrap.dedent(helpers if helpers is not None else self.helpers).strip()
        src = (helpers + "\n\n\n" if helpers else "") + f"{self.signature}\n{doc}\n{code}\n"
        return normalize(src)

    @property
    def reference(self) -> str:
        return self.assemble()

    def hand_mutants(self) -> list[tuple[str, str]]:
        return self._apply(self.hand)

    def hand_rewrites(self) -> list[tuple[str, str]]:
        return self._apply(self.rewrites)

    def _apply(self, edits) -> list[tuple[str, str]]:
        out = []
        raw = (textwrap.dedent(self.helpers).strip() + "\n\n\n" if self.helpers else "") + textwrap.dedent(self.body).strip()
        for desc, old, new in edits:
            if old not in raw:
                raise ValueError(f"{self.name}: hand mutant snippet not found: {old!r}")
            changed = raw.replace(old, new, 1)
            if self.helpers:
                helpers, body = changed.split("\n\n\n", 1)
            else:
                helpers, body = "", changed
            out.append((desc, self.assemble(body=body, helpers=helpers)))
        return out


def normalize(src: str) -> str:
    """Canonical formatting so mutants are indistinguishable from the reference by layout."""
    return ast.unparse(ast.parse(src)) + "\n"


SMALL = IntT(-10, 10)

BENCHMARKS: list[Benchmark] = [
    Benchmark(
        name="dips_below_zero",
        origin="HumanEval/3 (below_zero)",
        params=[("moves", ListT(SMALL, 6))],
        doc="""
            A wallet starts with balance 0. Apply the amounts in `moves` one at a time,
            in order (a positive amount is a deposit, a negative amount a withdrawal).
            Return True if the balance is strictly below 0 immediately after applying
            some amount, and False otherwise (including when `moves` is empty).
        """,
        body="""
            balance = 0
            for m in moves:
                balance += m
                if balance < 0:
                    return True
            return False
        """,
        hand=[("wallet starts at 1 instead of 0", "balance = 0", "balance = 1"),
              ("only the first five moves are checked", "for m in moves:", "for m in moves[:5]:")],
        rewrites=[("prefix sums recomputed with any()",
                   "balance = 0\nfor m in moves:\n    balance += m\n    if balance < 0:\n        return True\nreturn False",
                   "return any(sum(moves[:k + 1]) < 0 for k in range(len(moves)))")],
    ),
    Benchmark(
        name="has_near_pair",
        origin="HumanEval/0 (has_close_elements), integer version",
        params=[("vals", ListT(IntT(-20, 20), 6)), ("gap", IntT(0, 6))],
        doc="""
            Return True if there are two different positions i and j in `vals` whose
            values differ by strictly less than `gap` (that is, abs(vals[i] - vals[j]) < gap),
            and False otherwise.
        """,
        body="""
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    if abs(vals[i] - vals[j]) < gap:
                        return True
            return False
        """,
        hand=[("only compares neighbouring positions", "range(i + 1, len(vals))", "range(i + 1, min(i + 2, len(vals)))")],
    ),
    Benchmark(
        name="running_peak",
        origin="HumanEval/9 (rolling_max)",
        params=[("vals", ListT(SMALL, 6))],
        doc="""
            Return a list of the same length as `vals` whose element at position k is the
            largest value among vals[0], ..., vals[k]. An empty input gives an empty list.
        """,
        body="""
            out = []
            best = None
            for v in vals:
                if best is None or v > best:
                    best = v
                out.append(best)
            return out
        """,
        hand=[("peak initialised to 0 instead of the first value",
               "best = None\nfor v in vals:\n    if best is None or v > best:",
               "best = 0\nfor v in vals:\n    if v > best:")],
    ),
    Benchmark(
        name="weave",
        origin="HumanEval/5 (intersperse)",
        params=[("vals", ListT(IntT(-9, 9), 5)), ("sep", IntT(-9, 9))],
        doc="""
            Return a new list containing the elements of `vals` in order, with the value
            `sep` inserted between every two consecutive elements (and nowhere else).
        """,
        body="""
            out = []
            for i in range(len(vals)):
                if i > 0:
                    out.append(sep)
                out.append(vals[i])
            return out
        """,
    ),
    Benchmark(
        name="sum_and_product",
        origin="HumanEval/8 (sum_product)",
        params=[("vals", ListT(IntT(-6, 6), 5))],
        doc="""
            Return a pair (total, prod) where total is the sum of all values in `vals` and
            prod is the product of all values in `vals`. For an empty list the sum is 0
            and the product is 1.
        """,
        body="""
            total = 0
            prod = 1
            for v in vals:
                total += v
                prod *= v
            return (total, prod)
        """,
        hand=[("zeros are skipped in the product", "prod *= v", "prod = prod * v if v != 0 else prod")],
    ),
    Benchmark(
        name="is_prime",
        origin="HumanEval/31 (is_prime)",
        params=[("n", IntT(0, 250))],
        loop_bound=16,
        doc="""
            Return True if `n` is a prime number (an integer greater than 1 whose only
            positive divisors are 1 and itself), and False otherwise.
        """,
        body="""
            if n < 2:
                return False
            d = 2
            while d * d <= n:
                if n % d == 0:
                    return False
                d += 1
            return True
        """,
        hand=[("trial division stops one step early", "while d * d <= n:", "while d * d < n:")],
    ),
    Benchmark(
        name="largest_proper_divisor",
        origin="HumanEval/24 (largest_divisor)",
        params=[("n", IntT(2, 120))],
        loop_bound=120,
        doc="""
            Return the largest integer d with 1 <= d < n that divides `n` exactly.
        """,
        body="""
            best = 1
            for d in range(1, n):
                if n % d == 0:
                    best = d
            return best
        """,
        rewrites=[("search only up to n // 2", "range(1, n)", "range(1, n // 2 + 1)")],
    ),
    Benchmark(
        name="count_sevens",
        origin="HumanEval/36 (fizz_buzz)",
        params=[("n", IntT(0, 300))],
        loop_bound=300,
        doc="""
            Consider every integer i with 0 <= i < n that is divisible by 11 or by 13.
            Return the total number of times the digit 7 appears in the decimal
            representations of those integers.
        """,
        body="""
            count = 0
            for i in range(n):
                if i % 11 == 0 or i % 13 == 0:
                    x = i
                    while x > 0:
                        if x % 10 == 7:
                            count += 1
                        x //= 10
            return count
        """,
    ),
    Benchmark(
        name="is_leap",
        origin="business rule (Gregorian calendar)",
        params=[("year", IntT(1, 3000))],
        doc="""
            Return True if `year` is a leap year in the Gregorian calendar: years divisible
            by 4 are leap years, except years divisible by 100, which are not, except years
            divisible by 400, which are.
        """,
        body="""
            if year % 400 == 0:
                return True
            if year % 100 == 0:
                return False
            return year % 4 == 0
        """,
        hand=[("forgets the divisible-by-400 exception",
               "if year % 400 == 0:\n    return True\n", "")],
        rewrites=[("single boolean expression",
                   "if year % 400 == 0:\n    return True\nif year % 100 == 0:\n    return False\nreturn year % 4 == 0",
                   "return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)")],
    ),
    Benchmark(
        name="days_in_month",
        origin="business rule (Gregorian calendar)",
        params=[("month", IntT(1, 12)), ("year", IntT(1, 3000))],
        helpers="""
            def leap(y):
                return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        """,
        doc="""
            Return the number of days in month `month` (1 = January, ..., 12 = December) of
            year `year` in the Gregorian calendar. February has 29 days in leap years (years
            divisible by 4, except years divisible by 100 unless also divisible by 400) and
            28 otherwise; April, June, September and November have 30; all others have 31.
        """,
        body="""
            if month == 2:
                return 29 if leap(year) else 28
            if month in (4, 6, 9, 11):
                return 30
            return 31
        """,
        hand=[("leap rule ignores centuries", "y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)", "y % 4 == 0"),
              ("September treated as a 31-day month", "(4, 6, 9, 11)", "(4, 6, 11)")],
    ),
    Benchmark(
        name="triangle_kind",
        origin="classic testing example (triangle classification)",
        params=[("a", IntT(1, 15)), ("b", IntT(1, 15)), ("c", IntT(1, 15))],
        doc="""
            Classify side lengths a, b, c. Return 0 if they do not form a valid triangle,
            meaning some side is greater than or equal to the sum of the other two. Otherwise
            return 3 if all three sides are equal, 2 if exactly two sides are equal, and 1 if
            all sides are different.
        """,
        body="""
            if a + b <= c or a + c <= b or b + c <= a:
                return 0
            if a == b and b == c:
                return 3
            if a == b or b == c or a == c:
                return 2
            return 1
        """,
        hand=[("isosceles check misses a == c", "if a == b or b == c or a == c:", "if a == b or b == c:")],
    ),
    Benchmark(
        name="letter_grade",
        origin="business rule (grade bands)",
        params=[("score", IntT(0, 100))],
        doc="""
            Map an exam score to a grade point: 4 for a score of 90 or more, 3 for 80 to 89,
            2 for 70 to 79, 1 for 60 to 69, and 0 below 60.
        """,
        body="""
            if score >= 90:
                return 4
            if score >= 80:
                return 3
            if score >= 70:
                return 2
            if score >= 60:
                return 1
            return 0
        """,
        rewrites=[("arithmetic banding with clamping",
                   "if score >= 90:\n    return 4\nif score >= 80:\n    return 3\nif score >= 70:\n    return 2\nif score >= 60:\n    return 1\nreturn 0",
                   "return max(0, min(4, (score - 50) // 10))")],
    ),
    Benchmark(
        name="find_index",
        origin="binary search (classic)",
        params=[("xs", ListT(IntT(-20, 20), 7, sorted=True, distinct=True)), ("target", IntT(-20, 20))],
        loop_bound=5,
        doc="""
            `xs` is sorted in strictly increasing order. Return the position i such that
            xs[i] == target, or -1 if `target` does not occur in `xs`.
        """,
        body="""
            lo = 0
            hi = len(xs) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if xs[mid] == target:
                    return mid
                if xs[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid - 1
            return -1
        """,
        hand=[("loop stops when the range has one element left", "while lo <= hi:", "while lo < hi:")],
    ),
    Benchmark(
        name="merge_sorted",
        origin="merge step of merge sort (classic)",
        params=[("a", ListT(IntT(-9, 9), 4, sorted=True)), ("b", ListT(IntT(-9, 9), 4, sorted=True))],
        loop_bound=8,
        doc="""
            `a` and `b` are each sorted in non-decreasing order. Return a single list in
            non-decreasing order containing all elements of `a` and all elements of `b`
            (with repetitions kept).
        """,
        body="""
            i = 0
            j = 0
            out = []
            while i < len(a) and j < len(b):
                if a[i] <= b[j]:
                    out.append(a[i])
                    i += 1
                else:
                    out.append(b[j])
                    j += 1
            while i < len(a):
                out.append(a[i])
                i += 1
            while j < len(b):
                out.append(b[j])
                j += 1
            return out
        """,
        hand=[("forgets the leftover elements of b", "while j < len(b):\n    out.append(b[j])\n    j += 1\n", "")],
    ),
    Benchmark(
        name="unique_in_order",
        origin="HumanEval/26 (remove_duplicates) variant",
        params=[("xs", ListT(IntT(-5, 5), 6))],
        doc="""
            Return a list of the distinct values of `xs`, each appearing once, in the order of
            their first occurrence in `xs`.
        """,
        body="""
            out = []
            for x in xs:
                if x not in out:
                    out.append(x)
            return out
        """,
        hand=[("only removes adjacent repeats", "if x not in out:", "if not out or out[-1] != x:"),
              ("only checks the last three kept values", "if x not in out:", "if x not in out[-3:]:")],
    ),
    Benchmark(
        name="second_largest",
        origin="HumanEval/90 (next_smallest) variant",
        params=[("xs", ListT(IntT(-9, 9), 6))],
        doc="""
            Return the second largest distinct value in `xs`, that is, the largest value that
            is strictly smaller than max(xs). Return None if `xs` has fewer than two distinct
            values.
        """,
        body="""
            first = None
            second = None
            for x in xs:
                if first is None or x > first:
                    second = first
                    first = x
                elif x != first and (second is None or x > second):
                    second = x
            return second
        """,
        hand=[("repeated maximum is counted as a second value", "if first is None or x > first:", "if first is None or x >= first:")],
    ),
    Benchmark(
        name="best_window_sum",
        origin="maximum subarray (Kadane)",
        params=[("xs", ListT(SMALL, 6, min_len=1))],
        doc="""
            `xs` is non-empty. Return the largest possible sum of a non-empty run of
            consecutive elements of `xs`.
        """,
        body="""
            best = xs[0]
            cur = 0
            for x in xs:
                cur = max(x, cur + x)
                best = max(best, cur)
            return best
        """,
        hand=[("running sum is reset to 0 (empty runs allowed)", "cur = max(x, cur + x)", "cur = max(0, cur + x)")],
    ),
    Benchmark(
        name="rotate_left",
        origin="list rotation (classic)",
        params=[("xs", ListT(IntT(-9, 9), 6)), ("k", IntT(0, 12))],
        doc="""
            Return a new list equal to `xs` rotated left by `k` positions: the element at
            position i of the result is xs[(i + k) % len(xs)]. An empty list gives an empty
            list.
        """,
        body="""
            if not xs:
                return []
            k = k % len(xs)
            return xs[k:] + xs[:k]
        """,
        hand=[("rotation reduced modulo the maximum length 6 instead of len(xs)", "k = k % len(xs)", "k = k % 6")],
    ),
    Benchmark(
        name="longest_streak",
        origin="longest run (classic)",
        params=[("xs", ListT(IntT(0, 3), 7))],
        doc="""
            Return the length of the longest run of equal values in consecutive positions of
            `xs` (a single element is a run of length 1). Return 0 for an empty list.
        """,
        body="""
            if not xs:
                return 0
            best = 1
            run = 1
            for i in range(1, len(xs)):
                if xs[i] == xs[i - 1]:
                    run += 1
                    if run > best:
                        best = run
                else:
                    run = 1
            return best
        """,
        hand=[("best only updated when a run ends",
               "run += 1\n        if run > best:\n            best = run\n    else:\n        run = 1",
               "run += 1\n    else:\n        if run > best:\n            best = run\n        run = 1")],
    ),
    Benchmark(
        name="is_monotone",
        origin="HumanEval/57 (monotonic)",
        params=[("xs", ListT(IntT(-5, 5), 6))],
        doc="""
            Return True if `xs` is entirely non-decreasing or entirely non-increasing (lists
            with fewer than two elements count as both), and False otherwise.
        """,
        body="""
            inc = True
            dec = True
            for i in range(1, len(xs)):
                if xs[i] < xs[i - 1]:
                    inc = False
                if xs[i] > xs[i - 1]:
                    dec = False
            return inc or dec
        """,
    ),
    Benchmark(
        name="count_inversions",
        origin="inversion count (classic)",
        params=[("xs", ListT(IntT(-5, 5), 6))],
        doc="""
            Return the number of pairs of positions (i, j) with i < j and xs[i] > xs[j].
        """,
        body="""
            count = 0
            for i in range(len(xs)):
                for j in range(i + 1, len(xs)):
                    if xs[i] > xs[j]:
                        count += 1
            return count
        """,
        hand=[("only counts inversions at distance at most 3", "range(i + 1, len(xs))", "range(i + 1, min(i + 4, len(xs)))")],
    ),
    Benchmark(
        name="has_pair_sum",
        origin="HumanEval/43 (pairs_sum_to_zero) generalised",
        params=[("xs", ListT(SMALL, 6)), ("target", IntT(-20, 20))],
        doc="""
            Return True if there are two different positions i and j in `xs` with
            xs[i] + xs[j] == target, and False otherwise.
        """,
        body="""
            for i in range(len(xs)):
                for j in range(i + 1, len(xs)):
                    if xs[i] + xs[j] == target:
                        return True
            return False
        """,
        hand=[("an element may be paired with itself", "range(i + 1, len(xs))", "range(i, len(xs))"),
              ("pairs of equal values are ignored", "if xs[i] + xs[j] == target:", "if xs[i] + xs[j] == target and xs[i] != xs[j]:")],
        rewrites=[("complement looked up in the rest of the list",
                   "for j in range(i + 1, len(xs)):\n        if xs[i] + xs[j] == target:\n            return True",
                   "if target - xs[i] in xs[i + 1:]:\n        return True")],
    ),
    Benchmark(
        name="digit_sum",
        origin="HumanEval/66-style digit arithmetic",
        params=[("n", IntT(-9999, 9999))],
        loop_bound=5,
        doc="""
            Return the sum of the decimal digits of the absolute value of `n`
            (the digit sum of 0 is 0).
        """,
        body="""
            n = abs(n)
            total = 0
            while n > 0:
                total += n % 10
                n //= 10
            return total
        """,
    ),
    Benchmark(
        name="median_of_three",
        origin="median of three (classic)",
        params=[("a", IntT(-20, 20)), ("b", IntT(-20, 20)), ("c", IntT(-20, 20))],
        doc="""
            Return the median of the three integers a, b and c: the value that is in the
            middle once the three are sorted (ties allowed).
        """,
        body="""
            if a <= b <= c or c <= b <= a:
                return b
            if b <= a <= c or c <= a <= b:
                return a
            return c
        """,
        hand=[("misses a as the median when the values are in decreasing order",
               "if b <= a <= c or c <= a <= b:", "if b <= a <= c:")],
        rewrites=[("strict comparisons in the first test (ties fall through harmlessly)",
                   "if a <= b <= c or c <= b <= a:", "if a < b < c or c < b < a:")],
    ),
    Benchmark(
        name="bulk_price",
        origin="business rule (volume discount)",
        params=[("unit_cents", IntT(1, 500)), ("qty", IntT(1, 200))],
        doc="""
            Return the price in cents of `qty` items costing `unit_cents` each. The gross
            price is unit_cents * qty. Orders of 100 or more items get 15% off and orders of
            50 to 99 items get 10% off; the discount amount is rounded down to a whole number
            of cents and subtracted from the gross price.
        """,
        body="""
            gross = unit_cents * qty
            if qty >= 100:
                pct = 15
            elif qty >= 50:
                pct = 10
            else:
                pct = 0
            return gross - gross * pct // 100
        """,
    ),
    Benchmark(
        name="withdraw",
        origin="business rule (account withdrawal)",
        params=[("balance", IntT(0, 1000)), ("amount", IntT(0, 1000)), ("overdraft", BoolT())],
        doc="""
            Process a withdrawal of `amount` from an account holding `balance`. A withdrawal
            of 100 or more is free; a smaller withdrawal costs a fee of 2, also taken from
            the account. Reject the withdrawal (return None) if `amount` is not positive, or
            if the resulting balance would be below 0 when `overdraft` is False, or below
            -500 when `overdraft` is True. Otherwise return the resulting balance.
        """,
        body="""
            if amount <= 0:
                return None
            fee = 0 if amount >= 100 else 2
            new_balance = balance - amount - fee
            limit = -500 if overdraft else 0
            if new_balance < limit:
                return None
            return new_balance
        """,
        hand=[("fee waived from 99 instead of 100", "fee = 0 if amount >= 100 else 2", "fee = 0 if amount >= 99 else 2")],
    ),
    Benchmark(
        name="run_length",
        origin="run-length encoding (classic)",
        params=[("xs", ListT(IntT(0, 3), 5))],
        loop_bound=6,
        doc="""
            Run-length encode `xs`: split it into maximal runs of equal consecutive values and
            return a flat list [v1, c1, v2, c2, ...] where run number k consists of ck copies
            of the value vk, in order.
        """,
        body="""
            out = []
            i = 0
            while i < len(xs):
                j = i
                while j < len(xs) and xs[j] == xs[i]:
                    j += 1
                out.append(xs[i])
                out.append(j - i)
                i = j
            return out
        """,
    ),
]


def _net(comps, letters="abcde"):
    return "\n".join(f"if {letters[i]} > {letters[j]}:\n    {letters[i]}, {letters[j]} = {letters[j]}, {letters[i]}"
                     for i, j in comps)


_S4 = [(0, 1), (2, 3), (0, 2), (1, 3), (1, 2)]
_S5 = [(0, 1), (3, 4), (2, 4), (2, 3), (0, 3), (0, 2), (1, 4), (1, 3), (1, 2)]

# Harder tier: a witness has to be *constructed* (by search or careful simulation)
# rather than read off the changed line.
HARD: list[Benchmark] = [
    Benchmark(
        name="sort4", tier="hard", origin="sorting network (fixed comparator sequence)",
        params=[(c, IntT(0, 9)) for c in "abcd"],
        doc="Return the four integers a, b, c, d as a tuple in non-decreasing order.",
        body=_net(_S4) + "\nreturn (a, b, c, d)",
        hand=[("third comparator pairs a with d instead of a with c", _net([(0, 2)]), _net([(0, 3)])),
              ("fourth comparator pairs b with c instead of b with d", _net([(1, 3)]), _net([(1, 2)]))],
    ),
    Benchmark(
        name="sort5", tier="hard", origin="sorting network (9 comparators)",
        params=[(c, IntT(0, 5)) for c in "abcde"],
        doc="Return the five integers a, b, c, d, e as a tuple in non-decreasing order.",
        body=_net(_S5) + "\nreturn (a, b, c, d, e)",
        hand=[("comparator (c, e) replaced by (b, e)", _net([(2, 4)]), _net([(1, 4)])),
              ("comparator (b, d) missing", _net([(1, 3)]) + "\n", "")],
        rewrites=[("comparator (a, d) replaced by (a, e) (still a valid network)", _net([(0, 3)]), _net([(0, 4)]))],
    ),
    Benchmark(
        name="median5", tier="hard", origin="median selection by comparator network",
        params=[(c, IntT(0, 5)) for c in "abcde"],
        doc="Return the median of the five integers a, b, c, d, e (the third smallest, counting repeats).",
        body=_net(_S5) + "\nreturn c",
        hand=[("comparator (c, d) missing", _net([(2, 3)]) + "\n", ""),
              ("comparator (b, e) replaced by (b, d)", _net([(1, 4)]), _net([(1, 3)])),
              ("final comparator (b, c) dropped as an 'optimisation'", "\n" + _net([(1, 2)]), "")],
        rewrites=[("comparator (a, c) dropped as an optimisation (provably unnecessary for the median)",
                   _net([(0, 2)]) + "\n", "")],
    ),
    Benchmark(
        name="admit_requests", tier="hard", origin="sliding-window rate limiter",
        params=[("times", ListT(IntT(0, 12), 7, sorted=True))],
        doc="""
            `times` lists request arrival times in non-decreasing order. A rate limiter
            admits a request arriving at time t if fewer than 3 previously admitted requests
            arrived at times s with t - 5 < s <= t; otherwise the request is rejected (and
            does not count towards the limit). Return the number of admitted requests.
        """,
        body="""
            admitted = []
            for t in times:
                recent = 0
                for s in admitted:
                    if t - 5 < s:
                        recent += 1
                if recent < 3:
                    admitted.append(t)
            return len(admitted)
        """,
        hand=[("window includes requests exactly 5 units old", "if t - 5 < s:", "if t - 5 <= s:"),
              ("rejected requests also count towards the limit",
               "admitted = []\nfor t in times:\n    recent = 0\n    for s in admitted:\n        if t - 5 < s:\n            recent += 1\n    if recent < 3:\n        admitted.append(t)\nreturn len(admitted)",
               "seen = []\ncount = 0\nfor t in times:\n    recent = 0\n    for s in seen:\n        if t - 5 < s:\n            recent += 1\n    if recent < 3:\n        count += 1\n    seen.append(t)\nreturn count")],
    ),
    Benchmark(
        name="bucket_admits", tier="hard", origin="token-bucket rate limiter",
        params=[("times", ListT(IntT(0, 16), 6, sorted=True))],
        loop_bound=6,
        doc="""
            A token bucket holds at most 3 tokens and is full at time 0. A new token arrives at
            each of the times 4, 8, 12, 16, ...; a token that arrives when the bucket is full is
            discarded. Requests arrive at the times in `times` (non-decreasing). Tokens that
            arrive at the same time as a request arrive first. A request that finds at least
            one token takes one and is admitted; otherwise it is rejected. Return the number of
            admitted requests.
        """,
        body="""
            tokens = 3
            next_token = 4
            admitted = 0
            for t in times:
                while next_token <= t:
                    if tokens < 3:
                        tokens += 1
                    next_token += 4
                if tokens > 0:
                    tokens -= 1
                    admitted += 1
            return admitted
        """,
        hand=[("refill progress is lost: tokens are credited from the last request time",
               "tokens = 3\nnext_token = 4\nadmitted = 0\nfor t in times:\n    while next_token <= t:\n        if tokens < 3:\n            tokens += 1\n        next_token += 4\n    if tokens > 0:",
               "tokens = 3\nlast = 0\nadmitted = 0\nfor t in times:\n    tokens = min(3, tokens + (t - last) // 4)\n    last = t\n    if tokens > 0:"),
              ("a token arriving at the same time as a request comes too late", "while next_token <= t:", "while next_token < t:")],
    ),
    Benchmark(
        name="count_presses", tier="hard", origin="button debouncer (embedded)",
        params=[("samples", ListT(IntT(0, 1), 8))],
        doc="""
            `samples` are successive readings of a button (1 = pressed, 0 = released). A press is
            registered at the moment the button has read 1 for 3 consecutive readings. After a
            press is registered, another press can only be registered after at least one
            reading of 0. Return the number of registered presses.
        """,
        body="""
            presses = 0
            run = 0
            armed = True
            for x in samples:
                if x == 1:
                    run += 1
                    if run >= 3 and armed:
                        presses += 1
                        armed = False
                else:
                    run = 0
                    armed = True
            return presses
        """,
        hand=[("a 0 reading re-arms the button but does not reset the run of 1s",
               "else:\n        run = 0\n        armed = True", "else:\n        armed = True")],
        rewrites=[("armed flag replaced by an exact run-length test", "if run >= 3 and armed:\n            presses += 1\n            armed = False",
                   "if run == 3:\n            presses += 1\n            armed = False")],
    ),
    Benchmark(
        name="luhn_ok", tier="hard", origin="Luhn checksum (payment cards)",
        params=[("digits", ListT(IntT(0, 9), 6))],
        doc="""
            `digits` are the decimal digits of a card number, most significant first. Starting
            from the rightmost digit and moving left, double every second digit (the rightmost
            digit itself is not doubled); whenever a doubled value is greater than 9, subtract 9
            from it. Return True if the total of all resulting values is a multiple of 10, and
            False otherwise (an empty list counts as valid).
        """,
        body="""
            total = 0
            for i in range(len(digits)):
                d = digits[len(digits) - 1 - i]
                if i % 2 == 1:
                    d = d * 2
                    if d > 9:
                        d -= 9
                total += d
            return total % 10 == 0
        """,
        hand=[("subtracts 9 only above 10", "if d > 9:", "if d > 10:"),
              ("adds the doubled digit's tens and units only below 18", "if d > 9:\n            d -= 9", "if d > 9 and d < 18:\n            d -= 9")],
    ),
    Benchmark(
        name="weekday", tier="hard", origin="Zeller's congruence (calendar)",
        params=[("day", IntT(1, 28)), ("month", IntT(1, 12)), ("year", IntT(1801, 2199))],
        doc="""
            Return the day of the week of the Gregorian date day/month/year as an integer:
            0 = Saturday, 1 = Sunday, 2 = Monday, ..., 6 = Friday.
        """,
        body="""
            if month < 3:
                month += 12
                year -= 1
            k = year % 100
            j = year // 100
            return (day + 13 * (month + 1) // 5 + k + k // 4 + j // 4 + 5 * j) % 7
        """,
        hand=[("century taken before the January/February adjustment",
               "if month < 3:\n    month += 12\n    year -= 1\nk = year % 100\nj = year // 100",
               "j = year // 100\nif month < 3:\n    month += 12\n    year -= 1\nk = year % 100")],
    ),
    Benchmark(
        name="round_div", tier="hard", origin="banker's rounding (finance)",
        params=[("a", IntT(-60, 60)), ("b", IntT(1, 12))],
        doc="""
            Return a / b rounded to the nearest integer; when a / b is exactly halfway between
            two integers, return the even one (banker's rounding).
        """,
        body="""
            q = a // b
            r = a - q * b
            if 2 * r > b or (2 * r == b and q % 2 == 1):
                q += 1
            return q
        """,
        hand=[("rounds by truncating towards zero first",
               "q = a // b\nr = a - q * b",
               "q = abs(a) // b\nif a < 0:\n    q = -q\nr = a - q * b"),
              ("ties go up when the quotient is even", "q % 2 == 1", "q % 2 == 0")],
    ),
    Benchmark(
        name="can_split_evenly", tier="hard", origin="partition / subset-sum DP",
        params=[("xs", ListT(IntT(0, 6), 5))],
        loop_bound=16,
        doc="""
            Return True if the values in `xs` can be divided into two groups with equal sums,
            each value going to exactly one of the groups (a group may be empty), and False
            otherwise.
        """,
        body="""
            total = sum(xs)
            if total % 2 == 1:
                return False
            target = total // 2
            reachable = [True] + [False] * target
            for x in xs:
                for s in range(target, x - 1, -1):
                    if reachable[s - x]:
                        reachable[s] = True
            return reachable[target]
        """,
        hand=[("inner loop runs upwards, so a value can be used twice",
               "for s in range(target, x - 1, -1):", "for s in range(x, target + 1):"),
              ("inner loop stops one step early", "for s in range(target, x - 1, -1):", "for s in range(target, x, -1):")],
    ),
]

BENCHMARKS += HARD

BY_NAME = {b.name: b for b in BENCHMARKS}
