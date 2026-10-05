"""Conftest S4-strict — mock Ollama explicite pour CI verte.

Sans fallback silencieux, le pipeline exige un SLM. En tests/CI (sans Ollama),
on fournit un mock EXPLICITE (modèle `mock-ci`, jamais `template-s2`) pour que
la verte ne masque rien : les runs de bench S5 restent 100 % réels.
"""

import pytest

from backend.agents import tools

MOCK_MODEL = "mock-ci"

MOCK_OLLAMA_OK = {
    "ok": True,
    "response": "Explication mock en français : B105 détecté, externaliser le secret.",
    "prompt_tokens": 42,
    "tokens_out": 10,
    "tokens_per_sec": 20.0,
    "ttft_ms": 100,
    "load_ms": 5,
}


@pytest.fixture(autouse=True)
def mock_slm_ci(monkeypatch):
    """Mock SLM par défaut pour tous les tests (sauf override 503 explicite)."""
    monkeypatch.setenv("SLM_MODEL", MOCK_MODEL)
    monkeypatch.setattr(tools, "run_ollama", lambda prompt, model="": dict(MOCK_OLLAMA_OK))
