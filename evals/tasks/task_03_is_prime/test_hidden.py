from solution import is_prime


def test_primes():
    assert is_prime(2) is True
    assert is_prime(13) is True


def test_non_primes():
    assert is_prime(0) is False
    assert is_prime(1) is False
    assert is_prime(15) is False
    assert is_prime(-7) is False
