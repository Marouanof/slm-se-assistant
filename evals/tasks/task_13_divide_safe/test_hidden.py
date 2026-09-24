from solution import divide_safe


def test_ok():
    assert divide_safe(4, 2) == 2


def test_zero():
    assert divide_safe(1, 0) is None
