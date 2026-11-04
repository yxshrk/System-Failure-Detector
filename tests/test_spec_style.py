"""The spec-style classifier used in the SP3 analysis."""

import pytest

from premortem.sp1.spec_style import spec_style

CONSTRUCTIVE = [
    # compute the answer, compare at the end
    "def post(moves, result):\n    balance = 0\n    for m in moves:\n        balance += m\n"
    "        if balance < 0:\n            return result == True\n    return result == False\n",
    # element-wise comparison
    "def post(vals, result):\n    if len(result) != len(vals):\n        return False\n"
    "    for k in range(len(vals)):\n        if result[k] != max(vals[0:k + 1]):\n            return False\n    return True\n",
    # tuple unpacking of the result
    "def post(vals, result):\n    total, prod = result\n    return total == sum(vals) and prod == 0\n",
]

DECLARATIVE = [
    # sorted and a permutation of the input: properties only
    "def post(a, b, c, d, result):\n    r0, r1, r2, r3 = result\n    if not (r0 <= r1 <= r2 <= r3):\n"
    "        return False\n    return sorted([r0, r1, r2, r3]) == sorted([a, b, c, d])\n",
    "def post(xs, result):\n    return all(result[k] <= result[k + 1] for k in range(len(result) - 1))\n",
]


@pytest.mark.parametrize("spec", CONSTRUCTIVE)
def test_constructive(spec):
    assert spec_style(spec) == "constructive"


@pytest.mark.parametrize("spec", DECLARATIVE)
def test_declarative(spec):
    assert spec_style(spec) == "declarative"


def test_unparsable():
    assert spec_style("def pre(x):\n    return True\n") == "unparsable"
    assert spec_style("def post(:") == "unparsable"
