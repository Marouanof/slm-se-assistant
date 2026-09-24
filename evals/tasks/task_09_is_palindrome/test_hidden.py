from solution import is_palindrome


def test_true():
    assert is_palindrome("A man, a plan, a canal: Panama") is True


def test_false():
    assert is_palindrome("hello") is False
