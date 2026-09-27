"""Tests S2 — graphe LangGraph déterministe."""

from backend.agents.graph import run_pipeline
from backend.agents.tools import ALLOWED_TOOLS, search_symbols


def test_allow_list_figee():
    assert ALLOWED_TOOLS == ["read_file", "search_symbols", "run_ruff", "run_bandit", "run_pytest"]


def test_pipeline_algo_ok():
    r = run_pipeline(path="evals/tasks/task_01_factorial/solution.py")
    assert r["trajectoire"] == ["analyse", "tests", "revue", "humain"]
    assert r["status"] == "needs_review"
    assert r["model"] == "template-s2"
    assert any("[ok]" in f for f in r["findings"])


def test_pipeline_exec_bloquant():
    r = run_pipeline(path="evals/tasks/task_17_use_exec/solution.py")
    assert any("B102" in f for f in r["findings"]), r["findings"]
    assert "exec" in r["patch_proposal"].lower() or "ast.literal_eval" in r["patch_proposal"]


def test_pipeline_search_symbols():
    r = run_pipeline(code="def foo():\n    pass\n")
    assert "foo" in r.get("symbols", {}).get("functions", [])
    assert search_symbols("def bar(:")["functions"] == []
