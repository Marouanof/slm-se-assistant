from solution import reverse_words


def test_basic():
    assert reverse_words("hello world") == "world hello"


def test_spaces():
    assert reverse_words("  a   b ") == "b a"
