"""Test runner S1 — vérifie que le benchmark tourne sur 2 tâches."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_runner_limit2(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run(
        [sys.executable, "evals/run.py", "--limit", "2", "--out", str(out)],
        capture_output=True,
        text=True,
        timeout=120,
        shell=False,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 2
    for row in data:
        for key in ("task_id", "pass", "latency_ms", "tokens_in",
                    "tokens_out", "mem_mb", "ruff_count", "bandit_count"):
            assert key in row
    assert all(r["pass"] for r in data), data
