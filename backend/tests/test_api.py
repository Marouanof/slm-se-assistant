"""Tests S1/S2 — contrat backend (S1 conservé, S2 pipeline)."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_analyze_code_sale_detecte_ruff():
    # import non utilisé -> F401 attendu
    r = client.post("/analyze", json={"code": "import os\n\nx = 1\n"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert body["files"] == ["snippet.py"]
    codes = [i["code"] for i in body["ruff"]]
    assert any("F401" in c for c in codes), f"ruff attendu F401, got {codes}"


def test_analyze_traversee_refusee():
    r = client.post("/analyze", json={"path": "../PLAN_PROJET.txt"})
    assert r.status_code == 422


def test_tests_pipeline_smoke():
    r = client.post("/tests", json={"code": "x = 1\n"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert body["tests_pass"] is True
    assert body["trajectoire"] == ["analyse", "tests", "debug", "revue", "documentation", "devops", "humain"]
    assert body["model"] == "mock-ci"  # S4-strict : mock explicite conftest, jamais template-s2
    assert body["prompt_version"] == "v1"


def test_tests_traversee_refusee():
    r = client.post("/tests", json={"path": "../PLAN_PROJET.txt"})
    assert r.status_code == 422


def test_review_detecte_mot_de_passe():
    r = client.post("/review", json={"path": "evals/tasks/task_20_hardcoded_password/solution.py"})
    assert r.status_code == 200
    body = r.json()
    assert body["trajectoire"] == ["analyse", "tests", "debug", "revue", "documentation", "devops", "humain"]
    assert any("B105" in f for f in body["findings"]), f"B105 attendu, got {body['findings']}"
    assert body["status"] == "needs_review"
    g = client.get(f"/runs/{body['run_id']}")
    assert g.status_code == 200
    assert g.json()["result_summary"]["trajectoire"] == ["analyse", "tests", "debug", "revue", "documentation", "devops", "humain"]


def test_review_sans_secret_dans_audit():
    r = client.post("/review", json={"code": "api_key = 'sk-abcdefgh12345678'\nx = 1\n"})
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    g = client.get(f"/runs/{run_id}")
    assert "sk-abcdefgh12345678" not in g.json()["request_summary"].get("preview", "")


def test_runs_round_trip():
    r = client.post("/analyze", json={"code": "x = 1\n"})
    run_id = r.json()["run_id"]
    g = client.get(f"/runs/{run_id}")
    assert g.status_code == 200
    assert g.json()["id"] == run_id
    assert g.json()["endpoint"] == "/analyze"
