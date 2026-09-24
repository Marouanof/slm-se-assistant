from solution import roundtrip


def test_roundtrip():
    assert roundtrip({"a": 1}) == {"a": 1}
