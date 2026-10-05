"""Tests S4-strict — SLM obligatoire, fail-fast 503, aucun fallback template (CDC §4)."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.agents import tools
from backend.agents.graph import run_pipeline
from backend.main import app

client = TestClient(app)


def test_slm_requis_sans_env(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    with pytest.raises(HTTPException) as exc:
        tools.slm_model()
    assert exc.value.status_code == 503


def test_pipeline_sans_slm_503(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    with pytest.raises(HTTPException) as exc:
        run_pipeline(code="x = 1\n")
    assert exc.value.status_code == 503


def test_review_api_sans_slm_503(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    r = client.post("/review", json={"code": "x = 1\n"})
    assert r.status_code == 503
    assert "SLM_MODEL" in r.json()["detail"]


def test_tests_api_sans_slm_503(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    r = client.post("/tests", json={"code": "x = 1\n"})
    assert r.status_code == 503


def test_ollama_panne_503_explicite(monkeypatch):
    monkeypatch.setenv("SLM_MODEL", "mock-down")

    def _down(prompt, model=""):
        raise HTTPException(status_code=503, detail="Ollama indisponible (mock panne).")

    monkeypatch.setattr(tools, "run_ollama", _down)
    with pytest.raises(HTTPException) as exc:
        run_pipeline(path="evals/tasks/task_20_hardcoded_password/solution.py")
    assert exc.value.status_code == 503
    r = client.post("/review", json={"code": "x = 1\n"})
    assert r.status_code == 503


def test_slm_moque_succes():
    # Mock fourni par conftest (mock-ci) : pipeline complet avec explication SLM.
    r = run_pipeline(code="x = 1\n")
    assert r["llm_explanation"] != ""
    assert r["model"] == "mock-ci"
    assert r["slm_tokens_per_sec"] == 20.0
    assert r["status"] == "needs_review"


def test_review_api_moque_ok():
    r = client.post("/review", json={"path": "evals/tasks/task_20_hardcoded_password/solution.py"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_explanation"] != ""
    assert any("B105" in f for f in body["findings"])
    assert body["model"] == "mock-ci"
