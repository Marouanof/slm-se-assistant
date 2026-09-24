from solution import valid_parentheses


def test_valid():
    assert valid_parentheses("()[]{}") is True
    assert valid_parentheses("") is True


def test_invalid():
    assert valid_parentheses("(]") is False
    assert valid_parentheses("([)]") is False
