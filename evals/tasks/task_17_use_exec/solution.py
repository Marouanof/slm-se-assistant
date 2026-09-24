def run_code(code: str) -> dict:
    namespace: dict = {}
    exec(code, {}, namespace)  # noqa: S102 - volontairement vulnérable pour Bandit S1
    return namespace
