from solution import flatten_list


def test_flat():
    assert flatten_list([[1, 2], [3], 4]) == [1, 2, 3, 4]
    assert flatten_list([]) == []
