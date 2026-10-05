"""Backend FastAPI S4-strict — analyse Ruff/Bandit + pipeline SLM obligatoire (aucun fallback)."""

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agents import tools as agent_tools
from backend.agents.graph import MODEL_ID as _MODEL_ID
from backend.agents.graph import PROMPT_VERSION as _PROMPT_VERSION
from backend.agents.graph import run_pipeline
from backend.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BanditIssue,
    HealthResponse,
    ReviewResponse,
    RuffIssue,
    RunRecord,
    TestsResponse,
)

PROJECT_ROOT = agent_tools.PROJECT_ROOT
RUNS_DIR = PROJECT_ROOT / "runs"
RUNS_FILE = RUNS_DIR / "runs.json"
TOOL_TIMEOUT_S = agent_tools.TOOL_TIMEOUT_S

app = FastAPI(title="slm-se-assistant S4-strict", version="0.4.0-s4-strict")

# CORS S3 : UI Vite locale uniquement, jamais de wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


def redact(text: str) -> str:
    return agent_tools.redact(text)


def _load_runs() -> dict:
    if not RUNS_FILE.exists():
        return {}
    try:
        return json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_run(record: RunRecord) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_runs()
    data[record.id] = record.model_dump()
    RUNS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_error_run(endpoint: str, req_summary: dict, detail: str, latency_ms: int) -> str:
    """Loggue un run en échec SLM (503) pour garder l'audit LLMOps véridique."""
    run_id = uuid.uuid4().hex[:12]
    record = RunRecord(
        id=run_id,
        endpoint=endpoint,
        status="error",
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_summary=req_summary,
        result_summary={
            "error": redact(detail)[:500],
            "model": os.environ.get("SLM_MODEL", "").strip() or "missing",
            "prompt_version": _PROMPT_VERSION,
        },
    )
    _save_run(record)
    return run_id


def _resolve_project_path(raw: str) -> Path:
    # Délègue à l'allow-list S2 (même erreurs 422/404).
    return agent_tools.resolve_project_path(raw)


def _run_ruff(target: Path) -> list[RuffIssue]:
    # Compat S1 (evals/run.py) : convertit les dicts tools → modèles Pydantic.
    out: list[RuffIssue] = []
    for item in agent_tools._run_ruff(target):
        out.append(
            RuffIssue(
                code=str(item.get("code", "")),
                message=str(item.get("message", "")),
                filename=str(item.get("filename", "")),
                row=item.get("row"),
                col=item.get("col"),
            )
        )
    return out


def _run_bandit(target: Path) -> list[BanditIssue]:
    out: list[BanditIssue] = []
    for item in agent_tools._run_bandit(target):
        out.append(
            BanditIssue(
                test_id=str(item.get("test_id", "")),
                severity=str(item.get("severity", "")),
                confidence=str(item.get("confidence", "")),
                text=str(item.get("text", "")),
                filename=str(item.get("filename", "")),
                line_number=item.get("line_number"),
            )
        )
    return out


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]

    if req.code is not None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "snippet.py"
            target.write_text(req.code, encoding="utf-8")
            ruff_issues = _run_ruff(target)
            bandit_issues = _run_bandit(target)
        files = ["snippet.py"]
        req_summary = {"mode": "code", "code_len": len(req.code),
                       "preview": redact(req.code[:200])}
    else:
        assert req.path is not None
        target = _resolve_project_path(req.path)
        ruff_issues = _run_ruff(target)
        bandit_issues = _run_bandit(target)
        files = [str(target.relative_to(PROJECT_ROOT.resolve()))]
        req_summary = {"mode": "path", "path": redact(req.path)}

    latency_ms = int((time.perf_counter() - started) * 1000)
    record = RunRecord(
        id=run_id,
        endpoint="/analyze",
        status="ok",
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_summary=req_summary,
        result_summary={"files": files, "ruff_count": len(ruff_issues),
                        "bandit_count": len(bandit_issues)},
    )
    _save_run(record)
    return AnalyzeResponse(
        run_id=run_id, files=files, ruff=ruff_issues,
        bandit=bandit_issues, latency_ms=latency_ms,
    )


@app.post("/tests", response_model=TestsResponse)
def run_tests(req: AnalyzeRequest) -> TestsResponse:
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    if req.code is not None:
        req_summary: dict = {"mode": "code", "code_len": len(req.code), "preview": redact(req.code[:200])}
    else:
        req_summary = {"mode": "path", "path": redact(req.path or "")}
    try:
        # run_pipeline lève 422/404 si path invalide, 503 si SLM manquant/panne (S4-strict).
        result = run_pipeline(code=req.code, path=req.path)
    except HTTPException as exc:
        if exc.status_code == 503:
            _save_error_run("/tests", req_summary, str(exc.detail),
                            int((time.perf_counter() - started) * 1000))
        raise
    latency_ms = int((time.perf_counter() - started) * 1000)
    files = result.get("files", [])
    record = RunRecord(
        id=run_id,
        endpoint="/tests",
        status=str(result.get("status", "needs_review")),
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_summary=req_summary,
        result_summary={
            "files": files,
            "tests_pass": result.get("tests_pass"),
            "coverage_pct": result.get("coverage_pct"),
            "trajectoire": result.get("trajectoire", []),
            "model": result.get("model", _MODEL_ID),
            "prompt_version": result.get("prompt_version", _PROMPT_VERSION),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
        },
    )
    _save_run(record)
    return TestsResponse(
        run_id=run_id,
        files=files,
        tests_pass=bool(result.get("tests_pass")),
        coverage_pct=result.get("coverage_pct"),
        tests_output=str(result.get("tests_output", ""))[:2000],
        trajectoire=result.get("trajectoire", []),
        latency_ms=latency_ms,
        model=result.get("model", _MODEL_ID),
        prompt_version=result.get("prompt_version", _PROMPT_VERSION),
        status=str(result.get("status", "needs_review")),
    )


@app.post("/review", response_model=ReviewResponse)
def run_review(req: AnalyzeRequest) -> ReviewResponse:
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    if req.code is not None:
        req_summary = {"mode": "code", "code_len": len(req.code), "preview": redact(req.code[:200])}
    else:
        req_summary = {"mode": "path", "path": redact(req.path or "")}
    try:
        result = run_pipeline(code=req.code, path=req.path)
    except HTTPException as exc:
        if exc.status_code == 503:
            _save_error_run("/review", req_summary, str(exc.detail),
                            int((time.perf_counter() - started) * 1000))
        raise
    latency_ms = int((time.perf_counter() - started) * 1000)
    files = result.get("files", [])
    ruff_issues = [
        RuffIssue(
            code=str(i.get("code", "")),
            message=str(i.get("message", "")),
            filename=str(i.get("filename", "")),
            row=i.get("row"),
            col=i.get("col"),
        )
        for i in result.get("ruff", [])
    ]
    bandit_issues = [
        BanditIssue(
            test_id=str(i.get("test_id", "")),
            severity=str(i.get("severity", "")),
            confidence=str(i.get("confidence", "")),
            text=str(i.get("text", "")),
            filename=str(i.get("filename", "")),
            line_number=i.get("line_number"),
        )
        for i in result.get("bandit", [])
    ]
    record = RunRecord(
        id=run_id,
        endpoint="/review",
        status=str(result.get("status", "needs_review")),
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        request_summary=req_summary,
        result_summary={
            "files": files,
            "ruff_count": len(ruff_issues),
            "bandit_count": len(bandit_issues),
            "tests_pass": result.get("tests_pass"),
            "coverage_pct": result.get("coverage_pct"),
            "findings": result.get("findings", []),
            "debug_cause": result.get("debug_cause", ""),
            "documentation": str(result.get("documentation", ""))[:2000],
            "devops_verdict": result.get("devops_verdict", ""),
            "devops_notes": result.get("devops_notes", ""),
            "complexity": result.get("complexity", {}),
            "maintainability": result.get("maintainability", "n/a"),
            "llm_explanation": str(result.get("llm_explanation", ""))[:2000],
            "slm_tokens_in": result.get("slm_tokens_in", 0),
            "slm_tokens_out": result.get("slm_tokens_out", 0),
            "slm_tokens_per_sec": result.get("slm_tokens_per_sec", 0.0),
            "slm_ttft_ms": result.get("slm_ttft_ms", 0),
            "trajectoire": result.get("trajectoire", []),
            "model": result.get("model", _MODEL_ID),
            "prompt_version": result.get("prompt_version", _PROMPT_VERSION),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
        },
    )
    _save_run(record)
    return ReviewResponse(
        run_id=run_id,
        files=files,
        ruff=ruff_issues,
        bandit=bandit_issues,
        tests_pass=bool(result.get("tests_pass")),
        coverage_pct=result.get("coverage_pct"),
        tests_output=str(result.get("tests_output", ""))[:2000],
        findings=result.get("findings", []),
        patch_proposal=str(result.get("patch_proposal", "")),
        debug_cause=str(result.get("debug_cause", "")),
        documentation=str(result.get("documentation", ""))[:2000],
        devops_verdict=str(result.get("devops_verdict", "")),
        devops_notes=str(result.get("devops_notes", "")),
        complexity=result.get("complexity", {}),
        maintainability=str(result.get("maintainability", "n/a")),
        llm_explanation=str(result.get("llm_explanation", ""))[:2000],
        slm_tokens_per_sec=float(result.get("slm_tokens_per_sec", 0.0)),
        slm_ttft_ms=int(result.get("slm_ttft_ms", 0)),
        trajectoire=result.get("trajectoire", []),
        latency_ms=latency_ms,
        model=result.get("model", _MODEL_ID),
        prompt_version=result.get("prompt_version", _PROMPT_VERSION),
        status=str(result.get("status", "needs_review")),
    )


@app.get("/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str) -> RunRecord:
    data = _load_runs()
    if run_id not in data:
        raise HTTPException(status_code=404, detail=f"Run introuvable: {run_id}")
    return RunRecord(**data[run_id])


@app.get("/runs", response_model=list[RunRecord])
def list_runs(limit: int = 50) -> list[RunRecord]:
    data = _load_runs()
    records = [RunRecord(**v) for v in data.values()]
    records.sort(key=lambda r: r.created_at, reverse=True)
    return records[: max(1, min(limit, 200))]
