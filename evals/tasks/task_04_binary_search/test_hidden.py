from solution import binary_search


def test_found():
    assert binary_search([1, 2, 3, 4, 5], 3) == 2


def test_not_found():
    assert binary_search([1, 2, 3], 9) == -1


def test_empty():
    assert binary_search([], 1) == -1
