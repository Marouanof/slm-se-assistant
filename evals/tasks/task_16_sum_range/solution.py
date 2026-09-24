def sum_range(n: int) -> int:
    if n <= 0:
        return 0
    return sum(range(1, n + 1))
