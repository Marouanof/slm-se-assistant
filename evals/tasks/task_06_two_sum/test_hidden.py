from solution import two_sum


def test_found():
    assert two_sum([2, 7, 11, 15], 9) == [0, 1]


def test_none():
    assert two_sum([1, 2, 3], 99) == []
