from solution import run_code


def test_exec_runs():
    ns = run_code("x = 41 + 1")
    assert ns["x"] == 42
