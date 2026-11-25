"""Compare several benchmark runs: static metrics + sandbox execution metrics.

Produces one Markdown table per task (base vs fine-tuned vs ...). Execution
metrics are recomputed with the same sandbox for every run, so the comparison is
methodologically identical even when the original runs used
``EXECUTION_BACKEND="none"``.

Example:
    python compare_runs.py \
        --run-dir results/baseline/phi4mini/<id> --label base \
        --run-dir results/baseline/phi4mini_sft/<id> --label "SFT v1" \
        --run-dir results/baseline/phi4mini_sft_v2/<id> --label "SFT v2" \
        --private-dir datasets/private/test \
        --output comparison_v2.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_saved_outputs import (  # noqa: E402
    load_private,
    load_rows,
    score_code_task,
    score_unit_tests,
)

TASKS = [
    "code_generation",
    "code_explanation",
    "bug_detection",
    "code_refactoring",
    "unit_test_generation",
    "code_completion",
]


def _mean(values) -> float | None:
    values = [v for v in values if isinstance(v, (int, float))]
    return round(sum(values) / len(values), 4) if values else None


def static_metrics(run_dir: Path, task: str) -> dict:
    rows = load_rows(run_dir, task)
    evals = [row.get("eval") or {} for row in rows]
    out: dict = {"n": len(rows)}
    if task in ("code_generation", "code_refactoring"):
        out["compile_ok"] = _mean(e.get("compile_ok") for e in evals)
    if task == "code_refactoring":
        out["changed"] = _mean(e.get("changed") for e in evals)
    if task == "code_explanation":
        out["rouge_l"] = _mean(e.get("rouge_l") for e in evals)
        out["headings_ok"] = _mean(e.get("headings_ok") for e in evals)
    if task == "bug_detection":
        tp = sum(int(e.get("tp", 0)) for e in evals)
        fp = sum(int(e.get("fp", 0)) for e in evals)
        fn = sum(int(e.get("fn", 0)) for e in evals)
        tn = sum(int(e.get("tn", 0)) for e in evals)
        total = tp + fp + fn + tn
        out["accuracy"] = round((tp + tn) / total, 4) if total else None
        out["precision"] = round(tp / (tp + fp), 4) if tp + fp else None
        out["recall"] = round(tp / (tp + fn), 4) if tp + fn else None
        denom = 2 * tp + fp + fn
        out["f1"] = round(2 * tp / denom, 4) if denom else None
    if task == "unit_test_generation":
        out["syntax_ok"] = _mean(e.get("syntax_ok") for e in evals)
        out["avg_tests"] = _mean(e.get("n_tests") for e in evals)
    if task == "code_completion":
        out["exact_match"] = _mean(e.get("exact_match") for e in evals)
        out["edit_similarity"] = _mean(e.get("edit_similarity") for e in evals)
    return out


PRIMARY = {
    "code_generation": [("pass@1", "exec"), ("compile_ok", "static")],
    "code_explanation": [("rouge_l", "static"), ("headings_ok", "static")],
    "bug_detection": [("f1", "static"), ("accuracy", "static")],
    "code_refactoring": [("pass@1", "exec"), ("compile_ok", "static")],
    "unit_test_generation": [
        ("valid_suite_rate", "exec"),
        ("mutation_kill_rate", "exec"),
        ("syntax_ok", "static"),
    ],
    "code_completion": [("exact_match", "static"), ("edit_similarity", "static")],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", required=True)
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--private-dir", required=True, help="datasets/private/test")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if len(args.run_dir) != len(args.label):
        parser.error("--run-dir and --label must be given the same number of times")

    run_dirs = [Path(p) for p in args.run_dir]
    labels = args.label
    private_root = Path(args.private_dir)

    lines: list[str] = ["# Benchmark comparison", ""]
    for task in TASKS:
        private = load_private(private_root, task)
        static = {label: static_metrics(run_dir, task) for label, run_dir in zip(labels, run_dirs)}
        if task in ("code_generation", "code_refactoring"):
            exec_metrics = {
                label: score_code_task(run_dir, private, task, args.timeout)
                for label, run_dir in zip(labels, run_dirs)
            }
        elif task == "unit_test_generation":
            exec_metrics = {
                label: score_unit_tests(run_dir, private, args.timeout)
                for label, run_dir in zip(labels, run_dirs)
            }
        else:
            exec_metrics = {label: {} for label in labels}

        header = "| metric | " + " | ".join(labels) + " |"
        sep = "|---|" + "|".join(["---"] * len(labels)) + "|"
        lines += [f"## {task}", "", header, sep]
        for metric, kind in PRIMARY[task]:
            cells = []
            for label in labels:
                value = (exec_metrics[label] if kind == "exec" else static[label]).get(metric)
                cells.append("—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value))
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
        n = static[labels[0]]["n"]
        lines += ["", f"n = {n} problems per model.", ""]

    report = "\n".join(lines)
    print(report)
    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
        print("\nwrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
