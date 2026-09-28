"""Tests 6 agents — Debug, Documentation, DevOps (vague 1, déterministes)."""

from fastapi.testclient import TestClient

from backend.agents.graph import run_pipeline
from backend.main import app

client = TestClient(app)

TRAJ_7 = ["analyse", "tests", "debug", "revue", "documentation", "devops", "humain"]


def test_trajectoire_7_etapes():
    r = run_pipeline(path="evals/tasks/task_01_factorial/solution.py")
    assert r["trajectoire"] == TRAJ_7
    assert r["status"] == "needs_review"


def test_debug_cause_exec():
    r = run_pipeline(path="evals/tasks/task_17_use_exec/solution.py")
    assert "B102" in r["debug_cause"]
    assert "exec" in r["patch_proposal"].lower() or "ast.literal_eval" in r["patch_proposal"]


def test_debug_sain_sans_correctif():
    r = run_pipeline(code="x = 1\n")
    assert "aucun défaut" in r["debug_cause"].lower()
    assert r["patch_proposal"] == "Aucun correctif requis."


def test_documentation_liste_fonctions():
    r = run_pipeline(code="def foo():\n    pass\n")
    assert "foo" in r["documentation"]
    assert "## Fonctions" in r["documentation"]


def test_devops_verdict():
    r_ok = run_pipeline(path="evals/tasks/task_01_factorial/solution.py")
    assert r_ok["devops_verdict"] == "GO"
    r_ko = run_pipeline(path="evals/tasks/task_20_hardcoded_password/solution.py")
    assert r_ko["devops_verdict"] == "NO-GO"
    assert "bloquants=1" in r_ko["devops_notes"]


def test_review_expose_nouveaux_champs():
    r = client.post("/review", json={"path": "evals/tasks/task_20_hardcoded_password/solution.py"})
    assert r.status_code == 200
    body = r.json()
    assert "B105" in body["debug_cause"]
    assert "get_password" in body["documentation"]
    assert body["devops_verdict"] == "NO-GO"
    g = client.get(f"/runs/{body['run_id']}")
    assert g.json()["result_summary"]["devops_verdict"] == "NO-GO"
