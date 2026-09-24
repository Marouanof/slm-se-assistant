PASSWORD = "secret123"  # noqa: S105 - volontairement vulnérable pour Bandit S1


def get_password() -> str:
    return PASSWORD
