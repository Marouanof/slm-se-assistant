"""Backend FastAPI S1 — stubs déterministes + analyse Ruff/Bandit allow-listée."""

import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException

from backend.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BanditIssue,
    HealthResponse,
    RuffIssue,
    RunRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"
RUNS_FILE = RUNS_DIR / "runs.json"
TOOL_TIMEOUT_S = 30

app = FastAPI(title="slm-se-assistant S1", version="0.1.0-s1")

# Secrets à ne jamais logger ni renvoyer tels quels.
_SECRET_RES = [
    re.compile(r"sk-[A-Za-z0-9\-_]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(password|passwd|pwd|api[_-]?key|secret)\s*[:=]\s*\S+"),
]


def redact(text: str) -> str:
    out = text or ""
    for rx in _SECRET_RES:
        out = rx.sub("***REDACTED***", out)
    return out


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


def _resolve_project_path(raw: str) -> Path:
    if ".." in raw.replace("\\", "/").split("/"):
        raise HTTPException(status_code=422, detail="Traversée de chemin interdite ('..').")
    candidate = (PROJECT_ROOT / raw).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=422, detail="Chemin hors projet refusé.") from None
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable: {raw}")
    return candidate


def _run_ruff(target: Path) -> list[RuffIssue]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(target), "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_S,
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
        if not proc.stdout.strip():
            return []
        raw = json.loads(proc.stdout)
        issues: list[RuffIssue] = []
        for item in raw if isinstance(raw, list) else []:
            loc = item.get("location") or {}
            issues.append(
                RuffIssue(
                    code=str(item.get("code", "")),
                    message=redact(str(item.get("message", ""))),
                    filename=str(item.get("filename", "")),
                    row=loc.get("row"),
                    col=loc.get("column"),
                )
            )
        return issues
    except subprocess.TimeoutExpired:
        return [RuffIssue(code="RUFF_TIMEOUT", message="Ruff timeout 30s")]
    except Exception as exc:  # noqa: BLE001 - stub S1 robuste
        return [RuffIssue(code="RUFF_ERROR", message=redact(str(exc)))]


def _run_bandit(target: Path) -> list[BanditIssue]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "-f", "json", "-q", str(target)],
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_S,
            shell=False,
            cwd=str(PROJECT_ROOT),
        )
        if not proc.stdout.strip():
            return []
        raw = json.loads(proc.stdout)
        results = raw.get("results", []) if isinstance(raw, dict) else []
        issues: list[BanditIssue] = []
        for item in results:
            issues.append(
                BanditIssue(
                    test_id=str(item.get("test_id", "")),
                    severity=str(item.get("issue_severity", "")),
                    confidence=str(item.get("issue_confidence", "")),
                    text=redact(str(item.get("issue_text", ""))),
                    filename=str(item.get("filename", "")),
                    line_number=item.get("line_number"),
                )
            )
        return issues
    except subprocess.TimeoutExpired:
        return [BanditIssue(test_id="BANDIT_TIMEOUT", text="Bandit timeout 30s")]
    except Exception as exc:  # noqa: BLE001
        return [BanditIssue(test_id="BANDIT_ERROR", text=redact(str(exc)))]


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


@app.post("/tests", status_code=501)
def tests_stub() -> dict:
    return {"detail": "S2 - Test Generation non implémenté (stub S1)."}


@app.post("/review", status_code=501)
def review_stub() -> dict:
    return {"detail": "S2 - Code Review non implémenté (stub S1)."}


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
