"""Tests S1 — contrat backend stub."""

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


def test_tests_et_review_501():
    assert client.post("/tests").status_code == 501
    assert client.post("/review").status_code == 501


def test_runs_round_trip():
    r = client.post("/analyze", json={"code": "x = 1\n"})
    run_id = r.json()["run_id"]
    g = client.get(f"/runs/{run_id}")
    assert g.status_code == 200
    assert g.json()["id"] == run_id
    assert g.json()["endpoint"] == "/analyze"
