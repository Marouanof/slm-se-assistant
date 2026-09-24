"""Runner S1 — benchmark reproductible 20 tâches.

Mesure par tâche : pass/fail pytest, latence, tokens approx, mémoire, ruff/bandit.
Usage: python evals/run.py --limit 2 --out evals/results.json
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

EVALS_ROOT = Path(__file__).resolve().parent
TASKS_ROOT = EVALS_ROOT / "tasks"
PROJECT_ROOT = EVALS_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import _run_bandit, _run_ruff  # noqa: E402


def count_tokens(text: str) -> int:
    return len((text or "").split())


def run_pytest(task_dir: Path, tmp: Path) -> tuple[bool, str]:
    shutil.copy(task_dir / "solution.py", tmp / "solution.py")
    shutil.copy(task_dir / "test_hidden.py", tmp / "test_hidden.py")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_hidden.py", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
            cwd=str(tmp),
        )
        ok = proc.returncode == 0
        out = (proc.stdout + proc.stderr)[-2000:]
        return ok, out
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT 30s"
    except Exception as exc:  # noqa: BLE001
        return False, f"ERROR {exc}"


def run_task(task_dir: Path) -> dict:
    prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
    solution = (task_dir / "solution.py").read_text(encoding="utf-8")
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))

    mem_before = psutil.Process().memory_info().rss / 1024 / 1024 if psutil else 0.0
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        passed, output = run_pytest(task_dir, tmp)
        # Analyse statique de la solution de référence (réutilise backend S1).
        ruff_issues = _run_ruff(task_dir / "solution.py")
        bandit_issues = _run_bandit(task_dir / "solution.py")
    latency_ms = int((time.perf_counter() - started) * 1000)
    mem_after = psutil.Process().memory_info().rss / 1024 / 1024 if psutil else 0.0

    return {
        "task_id": task_dir.name,
        "category": meta.get("category", ""),
        "pass": passed,
        "latency_ms": latency_ms,
        "tokens_in": count_tokens(prompt),
        "tokens_out": count_tokens(solution),
        "mem_mb": round(max(mem_before, mem_after), 1),
        "ruff_count": len(ruff_issues),
        "bandit_count": len(bandit_issues),
        "output_tail": output[-500:],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", type=str, default="evals/results.json")
    args = ap.parse_args()

    tasks = sorted([p for p in TASKS_ROOT.iterdir() if p.is_dir()])[: args.limit]
    results = [run_task(t) for t in tasks]

    out_path = (PROJECT_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    n_pass = sum(1 for r in results if r["pass"])
    avg_lat = sum(r["latency_ms"] for r in results) / max(len(results), 1)
    print(f"{n_pass}/{len(results)} pass - latence moy {avg_lat:.0f}ms -> {out_path}")


if __name__ == "__main__":
    main()
