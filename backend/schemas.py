"""Schémas Pydantic S1/S2 — contrats stables pour agents S2 et UI S3."""

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class AnalyzeRequest(BaseModel):
    code: Optional[str] = Field(default=None, description="Snippet Python à analyser")
    path: Optional[str] = Field(default=None, description="Chemin relatif au projet")

    @model_validator(mode="after")
    def _at_least_one(self) -> "AnalyzeRequest":
        if not self.code and not self.path:
            raise ValueError("Fournir au moins 'code' ou 'path'.")
        return self


class RuffIssue(BaseModel):
    code: str
    message: str
    filename: str = ""
    row: Optional[int] = None
    col: Optional[int] = None


class BanditIssue(BaseModel):
    test_id: str = ""
    severity: str = ""
    confidence: str = ""
    text: str = ""
    filename: str = ""
    line_number: Optional[int] = None


class AnalyzeResponse(BaseModel):
    run_id: str
    files: list[str] = []
    ruff: list[RuffIssue] = []
    bandit: list[BanditIssue] = []
    latency_ms: int = 0


class TestsResponse(BaseModel):
    run_id: str
    files: list[str] = []
    tests_pass: bool = False
    coverage_pct: Optional[float] = None
    tests_output: str = ""
    trajectoire: list[str] = []
    latency_ms: int = 0
    model: str = "template-s2"
    prompt_version: str = "v1"
    status: str = "needs_review"


class ReviewResponse(BaseModel):
    run_id: str
    files: list[str] = []
    ruff: list[RuffIssue] = []
    bandit: list[BanditIssue] = []
    tests_pass: bool = False
    coverage_pct: Optional[float] = None
    tests_output: str = ""
    findings: list[str] = []
    patch_proposal: str = ""
    debug_cause: str = ""
    documentation: str = ""
    devops_verdict: str = "needs_review"
    devops_notes: str = ""
    trajectoire: list[str] = []
    latency_ms: int = 0
    model: str = "template-s2"
    prompt_version: str = "v1"
    status: str = "needs_review"


class HealthResponse(BaseModel):
    status: str = "ok"


class RunRecord(BaseModel):
    id: str
    endpoint: str
    status: str
    latency_ms: int = 0
    created_at: str = ""
    request_summary: dict[str, Any] = {}
    result_summary: dict[str, Any] = {}


class StubResponse(BaseModel):
    detail: str
