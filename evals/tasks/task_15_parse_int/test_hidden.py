from solution import parse_int


def test_ok():
    assert parse_int(" 42 ") == 42


def test_ko():
    assert parse_int("abc") is None
    assert parse_int("") is None
