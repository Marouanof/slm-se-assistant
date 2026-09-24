def flatten_list(nested: list) -> list:
    out: list = []
    for item in nested:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out
