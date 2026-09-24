from solution import unique_sorted


def test_basic():
    assert unique_sorted([3, 1, 2, 1]) == [1, 2, 3]
    assert unique_sorted([]) == []
