from solution import gcd


def test_basic():
    assert gcd(12, 18) == 6
    assert gcd(0, 5) == 5
    assert gcd(7, 7) == 7
