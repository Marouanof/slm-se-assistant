"""Tests S4-light — branchement SLM opt-in (revue seule, stdlib, fallback)."""

from backend.agents import tools
from backend.agents.graph import run_pipeline
from backend.agents.tools import run_ollama, slm_model


def test_slm_desactive_par_defaut(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    assert slm_model() == ""
    assert run_ollama("bonjour")["ok"] is False


def test_fallback_sans_slm(monkeypatch):
    monkeypatch.delenv("SLM_MODEL", raising=False)
    r = run_pipeline(code="x = 1\n")
    assert r["llm_explanation"] == ""
    assert r["model"] == "template-s2"
    assert r["status"] == "needs_review"


def test_slm_moque_succes(monkeypatch):
    monkeypatch.setenv("SLM_MODEL", "mock-model")
    monkeypatch.setattr(
        tools,
        "run_ollama",
        lambda prompt, model="": {
            "ok": True,
            "response": "Explication mock en français.",
            "prompt_tokens": 42,
            "tokens_out": 10,
            "tokens_per_sec": 20.0,
            "ttft_ms": 100,
            "load_ms": 5,
        },
    )
    r = run_pipeline(code="x = 1\n")
    assert r["llm_explanation"] == "Explication mock en français."
    assert r["model"] == "mock-model"
    assert r["slm_tokens_in"] == 42
    assert r["slm_tokens_per_sec"] == 20.0


def test_slm_moque_panne_fallback_deterministe(monkeypatch):
    monkeypatch.setenv("SLM_MODEL", "mock-down")
    monkeypatch.setattr(
        tools, "run_ollama", lambda prompt, model="": {"ok": False, "error": "connexion refusée"}
    )
    r = run_pipeline(path="evals/tasks/task_20_hardcoded_password/solution.py")
    assert r["llm_explanation"] == ""
    assert any("B105" in f for f in r["findings"])
    assert r["status"] == "needs_review"
