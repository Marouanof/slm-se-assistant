from solution import fibonacci


def test_base():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1


def test_values():
    assert fibonacci(2) == 1
    assert fibonacci(7) == 13
    assert fibonacci(10) == 55


def test_negative():
    import pytest

    with pytest.raises(ValueError):
        fibonacci(-3)
