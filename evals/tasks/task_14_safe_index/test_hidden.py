from solution import safe_index


def test_ok():
    assert safe_index([1, 2, 3], 1) == 2


def test_oob():
    assert safe_index([1], 5) is None
    assert safe_index([1], 5, default="x") == "x"
