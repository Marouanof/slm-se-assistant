from solution import count_vowels


def test_basic():
    assert count_vowels("hello") == 2
    assert count_vowels("AEIOU") == 5
    assert count_vowels("bcdf") == 0
