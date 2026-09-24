import pickle  # noqa: S403 - volontairement vulnérable pour Bandit S1


def roundtrip(obj: object) -> object:
    data = pickle.dumps(obj)
    return pickle.loads(data)  # noqa: S301
