import subprocess  # noqa: S404 - volontairement vulnérable pour Bandit S1


def run_echo() -> int:
    proc = subprocess.run("echo hi", shell=True, capture_output=True)  # noqa: S602
    return proc.returncode
