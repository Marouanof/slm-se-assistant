"""Aggregate baseline benchmark results into a comparison table (Mission 02.2).

Usage:
    python benchmark/scripts/aggregate_baseline.py --results <results_root>

Reads ``<task>_results.jsonl`` files recursively under the given tree
(``<mode_dir>/<model_dir>/<RUN_ID>/<task>_results.jsonl``) and also accepts
the legacy flat ``<short>_<task>_results.jsonl`` layout. Rows from separate
run directories are aggregated per (model, task, mode, run_id) so runs are
never silently mixed into a single number without provenance.

``MODE="full"`` is stored under ``results/baseline/``; the canonical mode is
read from each row. Rows with ``eval.skipped`` are counted as ``skipped`` and
the execution-dependent metric is emitted as ``null`` (not a misleading 0.0).

Writes comparison_summary.csv and comparison_summary.json to --out
(default: <results_root>/metadata).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict

TASKS = ["code_generation", "code_explanation", "bug_detection",
         "code_refactoring", "unit_test_generation", "code_completion"]


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def parse_model_task(path: Path, root: Path) -> tuple[str | None, str | None, str | None, str | None]:
    stem = path.name.replace("_results.jsonl", "")
    task = None
    model_from_name = None
    for t in TASKS:
        if stem == t:
            task = t
            break
        if stem.endswith(f"_{t}"):
            task = t
            model_from_name = stem[: -len(t) - 1]
            break
    if task is None:
        return None, None, None, None
    parts = path.relative_to(root).parts if path.is_relative_to(root) else path.parts
    mode = None
    model_dir = None
    run_id = None
    for i, part in enumerate(parts):
        if part in ("smoke_test", "baseline") and i + 2 < len(parts):
            mode = part
            model_dir = parts[i + 1]
            run_id = parts[i + 2] if i + 2 < len(parts) - 1 else None
            break
    if model_dir is None and parts:
        if root.name in ("smoke_test", "baseline") and parts[0] in ("qwen15", "qwen3", "phi4mini"):
            mode = root.name
            model_dir = parts[0]
            run_id = parts[1] if len(parts) >= 3 else None
        elif len(parts) == 1:
            full = path.parts
            for j, p in enumerate(full):
                if p in ("smoke_test", "baseline") and j + 3 < len(full):
                    mode = p
                    model_dir = full[j + 1]
                    run_id = full[j + 2]
                    break
    return (model_dir or model_from_name), task, mode, run_id


def compute_metrics(rows: list[dict], task: str) -> dict:
    n = len(rows)
    errors = sum(1 for r in rows if "error" in r)
    skipped = sum(1 for r in rows if (r.get("eval") or {}).get("skipped"))
    scored = sum(
        1 for r in rows
        if "error" not in r and not (r.get("eval") or {}).get("skipped")
    )
    latencies = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
    tpss = [r["tokens_per_s"] for r in rows if r.get("tokens_per_s") is not None]
    ttfts = [r["ttft_s"] for r in rows if r.get("ttft_s") is not None]
    vrams = [r["vram_gb"] for r in rows if r.get("vram_gb") is not None]

    evaluated = scored + skipped
    metrics: dict = {
        "n": n, "errors": errors, "scored": scored, "skipped": skipped,
        "evaluated": evaluated,
    }
    if latencies:
        metrics["avg_latency_s"] = sum(latencies) / len(latencies)
        metrics["total_latency_s"] = sum(latencies)
    if tpss:
        metrics["avg_tokens_per_s"] = sum(tpss) / len(tpss)
    if ttfts:
        metrics["avg_ttft_s"] = sum(ttfts) / len(ttfts)
    if vrams:
        metrics["max_vram_gb"] = max(vrams)

    # Task-specific aggregates. Tasks whose evaluation was skipped expose
    # None for the execution-dependent metric instead of a misleading 0.0.
    if task == "code_generation":
        passed = sum(1 for r in rows if (r.get("eval") or {}).get("tests_passed"))
        syntax_ok = sum(1 for r in rows if (r.get("eval") or {}).get("compile_ok"))
        metrics["pass_at_1"] = passed / scored if scored else None
        metrics["static_syntax_rate"] = syntax_ok / evaluated if evaluated else 0.0
        metrics["compile_rate"] = None  # generated code is not compiled or run
    elif task == "code_explanation":
        rouges = [r["eval"]["rouge_l"] for r in rows if (r.get("eval") or {}).get("rouge_l") is not None]
        metrics["avg_rouge_l"] = sum(rouges) / len(rouges) if rouges else None
        metrics["headings_rate"] = sum(1 for r in rows if (r.get("eval") or {}).get("headings_ok")) / n if n else 0.0
    elif task == "bug_detection":
        tp = sum(r.get("eval", {}).get("tp", 0) for r in rows)
        fp = sum(r.get("eval", {}).get("fp", 0) for r in rows)
        tn = sum(r.get("eval", {}).get("tn", 0) for r in rows)
        fn = sum(r.get("eval", {}).get("fn", 0) for r in rows)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        metrics.update({"precision": prec, "recall": rec, "f1": f1,
                        "tp": tp, "fp": fp, "tn": tn, "fn": fn})
    elif task == "code_refactoring":
        preserved = sum(1 for r in rows if (r.get("eval") or {}).get("behaviour_preserved"))
        changed = sum(1 for r in rows if (r.get("eval") or {}).get("changed"))
        syntax_ok = sum(1 for r in rows if (r.get("eval") or {}).get("compile_ok"))
        metrics["behaviour_preservation"] = preserved / scored if scored else None
        metrics["changed_rate"] = changed / evaluated if evaluated else 0.0
        metrics["static_syntax_rate"] = syntax_ok / evaluated if evaluated else 0.0
    elif task == "unit_test_generation":
        valid = sum(1 for r in rows if (r.get("eval") or {}).get("valid"))
        syntax_ok = sum(1 for r in rows if (r.get("eval") or {}).get("syntax_ok"))
        mut_scores = [r["eval"]["mutation_score"] for r in rows if (r.get("eval") or {}).get("mutation_score") is not None]
        metrics["validity_rate"] = valid / scored if scored else None
        metrics["avg_mutation_score"] = sum(mut_scores) / len(mut_scores) if mut_scores else None
        metrics["static_syntax_rate"] = syntax_ok / evaluated if evaluated else 0.0
        metrics["avg_n_tests"] = sum(r.get("eval", {}).get("n_tests", 0) for r in rows) / evaluated if evaluated else 0.0
    elif task == "code_completion":
        exact = sum(1 for r in rows if (r.get("eval") or {}).get("exact_match"))
        sims = [r["eval"]["edit_similarity"] for r in rows if "edit_similarity" in (r.get("eval") or {})]
        metrics["exact_match"] = exact / n if n else 0.0
        metrics["avg_edit_similarity"] = sum(sims) / len(sims) if sims else None
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True,
                        help="Root results/ directory (or a baseline/run subdirectory).")
    parser.add_argument("--out", default=None,
                        help="Output directory (default: <results>/metadata).")
    args = parser.parse_args()

    results_dir = Path(args.results)
    out_dir = Path(args.out) if args.out else (results_dir / "metadata")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group rows by (model, task, mode, run_id) so separate runs stay distinct.
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for path in sorted(results_dir.rglob("*_results.jsonl")):
        model, task, mode, run_id = parse_model_task(path, results_dir)
        if model is None or task is None:
            continue
        file_rows = load_rows(path)
        # Mission 02.2 records the canonical mode (full/smoke_test) in each
        # row; the directory for full is still named baseline/.
        if file_rows:
            row_mode = file_rows[0].get("mode")
            if row_mode:
                mode = row_mode
        key = (model, task, mode or "full", run_id or "flat")
        groups[key].extend(file_rows)

    # Also produce a per-(model, task, mode) rollup across runs of the same
    # model? No: keep run-level rows as the primary output to avoid mixing
    # sessions. The CSV carries run_id/mode columns for provenance.
    summary: dict[str, dict[str, dict]] = defaultdict(dict)
    flat_rows: list[tuple[str, str, str, str, dict]] = []
    for (model, task, mode, run_id), rows in sorted(groups.items()):
        if not rows:
            continue
        metrics = compute_metrics(rows, task)
        # Preserve run-level provenance in the JSON too: never collapse two
        # RUN_IDs of the same model/mode into one entry.
        summary[f"{model}/{mode}/{run_id}"][task] = metrics
        flat_rows.append((model, task, mode, run_id, metrics))

    csv_path = out_dir / "comparison_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "mode", "run_id", "task", "n", "errors", "scored", "skipped",
                         "evaluated", "avg_latency_s", "avg_ttft_s", "avg_tokens_per_s",
                         "max_vram_gb", "task_metrics_json"])
        for model, task, mode, run_id, m in flat_rows:
            writer.writerow([model, mode, run_id, task, m.get("n"), m.get("errors"),
                             m.get("scored"), m.get("skipped"), m.get("evaluated"),
                             m.get("avg_latency_s"), m.get("avg_ttft_s"),
                             m.get("avg_tokens_per_s"), m.get("max_vram_gb"),
                             json.dumps({k: v for k, v in m.items() if k not in
                                         {"n", "errors", "scored", "skipped", "evaluated",
                                          "avg_latency_s", "avg_ttft_s", "avg_tokens_per_s",
                                          "max_vram_gb"}})])

    json_path = out_dir / "comparison_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Wrote", csv_path)
    print("Wrote", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
