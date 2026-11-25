"""Validate baseline benchmark result files (Mission 02.2 layout).

Usage:
    python benchmark/scripts/validate_baseline_results.py --results <results_root>

``--results`` may point at a whole ``results/`` tree
(``smoke_test/ + baseline/ + metadata/``), at ``results/baseline``, or at a
single run directory. Files are found recursively and parsed as either the
new ``<task>_results.jsonl`` inside ``<mode_dir>/<model_dir>/<RUN_ID>/`` or the
legacy flat ``<short>_<task>_results.jsonl``. Duplicate IDs are errors
within one file but expected across separate run directories.

``MODE="full"`` is stored under ``results/baseline/``; the canonical mode
(``full``) is carried in each row. Rows whose ``eval.skipped`` is true are
valid: they record generated output without executing it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TASKS = ["code_generation", "code_explanation", "bug_detection",
         "code_refactoring", "unit_test_generation", "code_completion"]

REQUIRED_FIELDS = ["id", "task", "model", "input_tokens", "output_tokens", "latency_s", "output"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_model_task(path: Path, root: Path) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (model, task, mode, run_id) for a result file path.

    Handles --results pointing at results/, results/baseline, or a single
    run directory, plus the legacy flat layout.
    """
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

    # Walk parents to find mode/model/run in the Mission 02.1 layout.
    parts = path.relative_to(root).parts if path.is_relative_to(root) else path.parts
    mode = None
    model_dir = None
    run_id = None
    for i, part in enumerate(parts):
        if part in ("smoke_test", "baseline") and i + 2 < len(parts):
            mode = part
            model_dir = parts[i + 1]
            # Next component is the run id unless the file sits directly
            # under the model dir.
            run_id = parts[i + 2] if i + 2 < len(parts) - 1 else None
            break
    if model_dir is None and parts:
        # Root is results/baseline (or smoke_test): [model, run, file].
        if root.name in ("smoke_test", "baseline") and parts[0] in ("qwen15", "qwen3", "phi4mini"):
            mode = root.name
            model_dir = parts[0]
            run_id = parts[1] if len(parts) >= 3 else None
        elif len(parts) == 1:
            # Root is a single run dir: infer from full path parents.
            full = path.parts
            # .../<mode>/<model>/<run>/<file>
            for j, p in enumerate(full):
                if p in ("smoke_test", "baseline") and j + 3 < len(full):
                    mode = p
                    model_dir = full[j + 1]
                    run_id = full[j + 2]
                    break
    model = model_dir or model_from_name
    return model, task, mode, run_id


def verify_sha256(root: Path, warnings: list[str]) -> None:
    # Accept --results at results/ or results/baseline: search the root, its
    # metadata/ subdir, and the parent results/ dir.
    candidates = [
        root / "SHA256SUMS.txt",
        root / "metadata" / "SHA256SUMS.txt",
        root.parent / "SHA256SUMS.txt",
        root.parent / "metadata" / "SHA256SUMS.txt",
    ]
    sums = next((p for p in candidates if p.is_file()), None)
    # Hash paths are relative to the sums file's enclosing results/ dir.
    sums_base = None
    if sums is not None:
        # Hash paths are relative to RESULTS_ROOT (results/). A sums file at
        # results/SHA256SUMS.txt has base results/; at results/metadata/
        # SHA256SUMS.txt the base is one level up.
        sums_base = sums.parent.parent if sums.parent.name == "metadata" else sums.parent
    if sums is None or sums_base is None:
        warnings.append("No SHA256SUMS.txt found; hash verification skipped.")
        return
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            warnings.append(f"Malformed SHA256SUMS line: {line!r}")
            continue
        expected, rel = parts
        # When validating a subtree (baseline/ or smoke_test/), skip entries
        # for the other subtree instead of warning.
        if root.name in ("baseline", "smoke_test") and rel.split("/")[0] not in (root.name,):
            continue
        target = sums_base.joinpath(*rel.split("/"))
        if not target.is_file():
            warnings.append(f"SHA256SUMS lists missing file: {rel}")
            continue
        if sha256_file(target) != expected:
            warnings.append(f"Hash mismatch: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--check-sha256", action="store_true",
                        help="Also verify SHA256SUMS.txt hashes.")
    args = parser.parse_args()

    results_dir = Path(args.results)
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, dict] = {}

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return 1

    candidates = sorted(results_dir.rglob("*_results.jsonl"))
    if not candidates:
        print(f"No *_results.jsonl files under {results_dir}")
        return 1

    for path in candidates:
        model, task, mode, run_id = parse_model_task(path, results_dir)
        if model is None or task is None:
            warnings.append(f"Skipping unrecognised file: {path.relative_to(results_dir)}")
            continue
        label = f"{model}/{task}" + (f" [{mode}/{run_id}]" if mode else "")
        rel = str(path.relative_to(results_dir))
        rows: list[dict] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{rel}:{line_no} invalid JSON: {e}")
                continue
            rows.append(row)
            if "error" in row:
                warnings.append(f"{rel}:{line_no} error row id={row.get('id')}")
                continue
            for field in REQUIRED_FIELDS:
                if field not in row:
                    errors.append(f"{rel}:{line_no} missing field '{field}'")
            if "eval" not in row:
                warnings.append(f"{rel}:{line_no} missing 'eval'")
            # Mission 02.2 rows must carry run provenance.
            if "run_id" not in row:
                warnings.append(f"{rel}:{line_no} missing 'run_id' (pre-02.2 file?)")
        ids = [r.get("id") for r in rows]
        if len(ids) != len(set(ids)):
            errors.append(f"{rel} duplicate IDs")
        summary[label] = {"rows": len(rows), "unique_ids": len(set(ids)), "path": rel}

    if args.check_sha256:
        verify_sha256(results_dir, warnings)

    print("Validation errors:", len(errors))
    for e in errors[:30]:
        print("  ERROR:", e)
    print("Validation warnings:", len(warnings))
    for w in warnings[:30]:
        print("  WARN :", w)
    print("Files summary:")
    for k, v in sorted(summary.items()):
        print(f"  {k}: {v['rows']} rows, {v['unique_ids']} unique")

    out = results_dir / "validation_report.json"
    out.write_text(json.dumps({"errors": errors, "warnings": warnings, "summary": summary}, indent=2), encoding="utf-8")
    print("Wrote", out)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
