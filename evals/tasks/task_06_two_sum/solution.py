def two_sum(nums: list[int], target: int) -> list[int]:
    seen: dict[int, int] = {}
    for i, v in enumerate(nums):
        need = target - v
        if need in seen:
            return [seen[need], i]
        seen[v] = i
    return []
