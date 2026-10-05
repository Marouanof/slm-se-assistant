"""État partagé du graphe S2 — déterministe, extensible pour LLM S4."""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """État circulant entre Analyse → Tests → Debug → Revue → Documentation → DevOps → Humain."""

    input_code: str | None
    input_path: str | None
    files: list[str]
    code_len: int
    ruff: list[dict[str, Any]]
    bandit: list[dict[str, Any]]
    symbols: dict[str, Any]
    complexity: dict[str, Any]
    maintainability: str
    tests_pass: bool | None
    coverage_pct: float | None
    tests_output: str
    findings: list[str]
    patch_proposal: str
    debug_cause: str
    documentation: str
    devops_verdict: str
    devops_notes: str
    llm_explanation: str
    slm_tokens_in: int
    slm_tokens_out: int
    slm_tokens_per_sec: float
    slm_ttft_ms: int
    trajectoire: list[str]
    latency_ms: int
    tokens_in: int
    tokens_out: int
    model: str
    prompt_version: str
    status: str
