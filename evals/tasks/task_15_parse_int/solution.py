def parse_int(s: str):
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None
