"""Execution-based metrics for saved model outputs (CPU only).

Reads a results run directory (the ones produced by the benchmark notebooks),
extracts the generated code, and runs it through the isolated sandbox against
the hidden reference tests. No GPU and no model inference: this scores outputs
that are already on disk.

Example:
    python eval_saved_outputs.py \
        --run-dir results/baseline/phi4mini/<run_id> \
        --run-dir results/baseline/phi4mini_sft/<run_id> \
        --labels base sft \
        --private-dir datasets/private/test \
        --output-json execution_metrics.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox_runner import (  # noqa: E402
    run_code_generation,
    run_code_refactoring,
    run_unit_tests,
)

_CODE_FENCE = re.compile(
    r"```(?:python|py|python3)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE
)


def extract_code_block(text: str) -> str:
    match = _CODE_FENCE.search(text)
    if match:
        return match.group(1).strip("\n")
    return text.strip()


def strip_marker(text: str) -> str:
    """Drop the fine-tuned model's trailing ``|`` marker and refactor notes."""
    text = text.rstrip()
    if "### Changes" in text:
        text = text.split("### Changes")[0].rstrip()
    text = re.sub(r"\|[^\n]*$", "", text).rstrip()
    return text


def load_rows(run_dir: Path, task: str) -> list[dict]:
    path = run_dir / f"{task}_results.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_private(private_dir: Path, task: str) -> dict[str, dict]:
    rows = {}
    for line in (private_dir / f"{task}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def score_code_task(run_dir: Path, private: dict, task: str, timeout: int) -> dict:
    runner = run_code_generation if task == "code_generation" else run_code_refactoring
    n = passed = 0
    failures: dict[str, int] = {}
    for row in load_rows(run_dir, task):
        pid = row["id"]
        if pid not in private:
            continue
        n += 1
        code = extract_code_block(strip_marker(row["output"]))
        result = runner(code, private[pid]["reference_tests"], timeout=timeout)
        if result["pass@1"]:
            passed += 1
        else:
            reason = result["reason"]
            if reason == "ok":
                tail = result["stderr_tail"].splitlines()
                reason = tail[-1][:80] if tail else "unknown"
            failures[reason] = failures.get(reason, 0) + 1
    return {
        "n": n,
        "passed": passed,
        "pass@1": round(passed / n, 4) if n else None,
        "failures": dict(sorted(failures.items(), key=lambda item: -item[1])[:5]),
    }


def score_unit_tests(run_dir: Path, private: dict, timeout: int) -> dict:
    n = valid = 0
    total_mutants = killed = perfect = 0
    for row in load_rows(run_dir, "unit_test_generation"):
        pid = row["id"]
        if pid not in private:
            continue
        n += 1
        record = private[pid]
        artifacts = record.get("private_artifacts") or {}
        canonical = artifacts.get("canonical_solution")
        mutants = artifacts.get("mutants") or []
        if not canonical:
            continue
        tests = extract_code_block(strip_marker(row["output"]))
        result = run_unit_tests(
            tests, canonical, record["reference_tests"], mutants=mutants, timeout=timeout
        )
        if not result.get("tests_pass_on_canonical"):
            continue
        valid += 1
        n_mutants = result.get("n_mutants", 0)
        n_killed = result.get("mutants_killed", 0)
        total_mutants += n_mutants
        killed += n_killed
        if n_mutants and n_killed == n_mutants:
            perfect += 1
    return {
        "n": n,
        "valid_suites": valid,
        "valid_suite_rate": round(valid / n, 4) if n else None,
        "mutants_total": total_mutants,
        "mutants_killed": killed,
        "mutation_kill_rate": round(killed / total_mutants, 4) if total_mutants else None,
        "problems_with_all_mutants_killed": perfect,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", required=True, help="results run directory (repeatable)")
    parser.add_argument("--labels", nargs="*", default=None, help="label per --run-dir")
    parser.add_argument("--private-dir", required=True, help="path to datasets/private/test")
    parser.add_argument(
        "--tasks",
        nargs="*",
        default=["code_generation", "code_refactoring", "unit_test_generation"],
    )
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    run_dirs = [Path(p) for p in args.run_dir]
    labels = args.labels or [path.parent.name for path in run_dirs]
    if len(labels) != len(run_dirs):
        parser.error("--labels must have the same length as --run-dir")
    private_dir = Path(args.private_dir)

    summary: dict[str, dict[str, dict]] = {}
    for task in args.tasks:
        private = load_private(private_dir, task)
        summary[task] = {}
        for label, run_dir in zip(labels, run_dirs):
            print(f"[{task}] {label} ({run_dir}) ...", end=" ", flush=True)
            if task in ("code_generation", "code_refactoring"):
                result = score_code_task(run_dir, private, task, args.timeout)
            else:
                result = score_unit_tests(run_dir, private, args.timeout)
            summary[task][label] = result
            print(json.dumps(result), flush=True)

    if args.output_json:
        Path(args.output_json).write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
