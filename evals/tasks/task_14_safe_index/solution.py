def safe_index(lst: list, i: int, default=None):
    try:
        return lst[i]
    except IndexError:
        return default
