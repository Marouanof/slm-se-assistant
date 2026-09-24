from solution import sum_range


def test_values():
    assert sum_range(5) == 15
    assert sum_range(0) == 0
    assert sum_range(-3) == 0
