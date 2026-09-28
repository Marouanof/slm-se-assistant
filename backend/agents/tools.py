"""Outils allow-list S2 — Ruff/Bandit déplacés depuis main.py + read/search/pytest.

Aucun shell libre : seuls subprocess avec argv fixe, shell=False, cwd contrôlé.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL_TIMEOUT_S = 30
SLM_TIMEOUT_S = 120
SLM_HOST = os.environ.get("SLM_HOST", "http://localhost:11434").rstrip("/")


def slm_model() -> str:
    """Nom du SLM actif (env SLM_MODEL), "" si désactivé (défaut déterministe)."""
    name = os.environ.get("SLM_MODEL", "").strip()
    return "" if name in ("", "template-s2") else name


def run_ollama(prompt: str, model: str = "", timeout_s: int = SLM_TIMEOUT_S) -> dict:
    """Appelle Ollama via httpx (dépendance déjà épinglée, pas de SDK Ollama).

    Champs API lus : response, prompt_eval_count, eval_count, eval_duration,
    prompt_eval_duration (proxy TTFT), load_duration. Jamais d'exception bloquante.
    """
    model = model or slm_model()
    if not model:
        return {"ok": False, "error": "SLM désactivé (SLM_MODEL non défini)"}
    try:
        resp = httpx.post(
            SLM_HOST + "/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0}},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 - panne Ollama = fallback, jamais de crash
        return {"ok": False, "error": redact(str(exc))[:200]}
    eval_count = int(data.get("eval_count") or 0)
    eval_dur = int(data.get("eval_duration") or 0)
    tps = round(eval_count / eval_dur * 1e9, 1) if eval_dur > 0 else 0.0
    return {
        "ok": True,
        "response": redact(str(data.get("response", "")))[:2000],
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "tokens_out": eval_count,
        "tokens_per_sec": tps,
        "ttft_ms": int(int(data.get("prompt_eval_duration") or 0) // 1_000_000),
        "load_ms": int(int(data.get("load_duration") or 0) // 1_000_000),
    }

ALLOWED_TOOLS = ["read_file", "search_symbols", "run_ruff", "run_bandit", "run_pytest"]

_SECRET_RES = [
    re.compile(r"sk-[A-Za-z0-9\-_]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(password|passwd|pwd|api[_-]?key|secret)\s*[:=]\s*\S+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.~+/=]{8,}"),
]


def redact(text: str) -> str:
    out = text or ""
    for rx in _SECRET_RES:
        out = rx.sub("***REDACTED***", out)
    return out


def count_tokens(text: str) -> int:
    return len((text or "").split())


def resolve_project_path(raw: str) -> Path:
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


def read_file(path: str, max_chars: int = 20000) -> str:
    """Lecture sécurisée d'un fichier relatif au projet."""
    target = resolve_project_path(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars]


def search_symbols(code: str) -> dict:
    """Recherche de symboles via AST, sans shell. Retourne funcs/classes/imports."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError as exc:
        return {"error": f"SyntaxError: {exc}", "functions": [], "classes": [], "imports": []}
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imports.append(n.module or "")
    return {"functions": funcs, "classes": classes, "imports": imports}


def _run_ruff(target: Path) -> list[dict]:
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
        out = []
        for item in raw if isinstance(raw, list) else []:
            loc = item.get("location") or {}
            out.append(
                {
                    "code": str(item.get("code", "")),
                    "message": redact(str(item.get("message", ""))),
                    "filename": str(item.get("filename", "")),
                    "row": (loc.get("row")),
                    "col": (loc.get("column")),
                }
            )
        return out
    except subprocess.TimeoutExpired:
        return [{"code": "RUFF_TIMEOUT", "message": "Ruff timeout 30s", "filename": "", "row": None, "col": None}]
    except Exception as exc:  # noqa: BLE001 - robustesse déterministe
        return [{"code": "RUFF_ERROR", "message": redact(str(exc)), "filename": "", "row": None, "col": None}]


def _run_bandit(target: Path) -> list[dict]:
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
        out = []
        for item in results:
            out.append(
                {
                    "test_id": str(item.get("test_id", "")),
                    "severity": str(item.get("issue_severity", "")),
                    "confidence": str(item.get("issue_confidence", "")),
                    "text": redact(str(item.get("issue_text", ""))),
                    "filename": str(item.get("filename", "")),
                    "line_number": item.get("line_number"),
                }
            )
        return out
    except subprocess.TimeoutExpired:
        return [{"test_id": "BANDIT_TIMEOUT", "text": "Bandit timeout 30s"}]
    except Exception as exc:  # noqa: BLE001
        return [{"test_id": "BANDIT_ERROR", "text": redact(str(exc))}]


_SMOKE_TEST = '''"""Tests smoke générés S2 (templates déterministes)."""
import solution

def test_solution_imports():
    assert solution is not None

def test_solution_compiles():
    import py_compile
    py_compile.compile("solution.py", doraise=True)
'''


def _write_smoke(tmp: Path) -> None:
    (tmp / "test_smoke.py").write_text(_SMOKE_TEST, encoding="utf-8")


def run_pytest_tmp(code: str, timeout_s: int = TOOL_TIMEOUT_S) -> dict:
    """Exécute pytest + coverage en dossier temporaire. Jamais de shell libre."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "solution.py").write_text(code or "", encoding="utf-8")
        _write_smoke(tmp)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_smoke.py", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                shell=False,
                cwd=str(tmp),
            )
            passed = proc.returncode == 0
            output = (proc.stdout + proc.stderr)[-2000:]
        except subprocess.TimeoutExpired:
            return {"tests_pass": False, "coverage_pct": None, "output": "TIMEOUT 30s"}
        except Exception as exc:  # noqa: BLE001
            return {"tests_pass": False, "coverage_pct": None, "output": redact(str(exc))[-2000:]}
        # Couverture : best-effort, non bloquante.
        coverage_pct: float | None = None
        try:
            subprocess.run(
                [sys.executable, "-m", "coverage", "run", "-m", "pytest", "test_smoke.py", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                shell=False,
                cwd=str(tmp),
            )
            rep = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", "-"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                shell=False,
                cwd=str(tmp),
            )
            if rep.stdout.strip():
                data = json.loads(rep.stdout)
                coverage_pct = float(data.get("totals", {}).get("percent_covered", 0.0))
        except Exception:  # noqa: BLE001 - couverture optionnelle
            coverage_pct = None
        return {"tests_pass": passed, "coverage_pct": coverage_pct, "output": redact(output)[-2000:]}


def run_pytest_path(path: str, timeout_s: int = TOOL_TIMEOUT_S) -> dict:
    """Variante path : copie le fichier projet en tmp puis même pipeline."""
    target = resolve_project_path(path)
    code = target.read_text(encoding="utf-8", errors="replace")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copy(target, tmp / "solution.py")
        _write_smoke(tmp)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_smoke.py", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                shell=False,
                cwd=str(tmp),
            )
            passed = proc.returncode == 0
            output = (proc.stdout + proc.stderr)[-2000:]
        except subprocess.TimeoutExpired:
            return {"tests_pass": False, "coverage_pct": None, "output": "TIMEOUT 30s"}
        return {"tests_pass": passed, "coverage_pct": None, "output": redact(output)[-2000:], "code": code}
