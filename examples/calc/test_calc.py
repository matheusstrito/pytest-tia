import pytest

from calc import add, sub, mul, div


def test_add():
    assert add(2, 3) == 5


def test_sub():
    assert sub(10, 4) == 6


def test_mul():
    assert mul(6, 7) == 42


def test_div():
    assert div(9, 3) == 3


def test_div_by_zero():
    with pytest.raises(ZeroDivisionError):
        div(1, 0)
