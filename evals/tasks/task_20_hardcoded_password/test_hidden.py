from solution import get_password


def test_password():
    assert get_password() == "secret123"
