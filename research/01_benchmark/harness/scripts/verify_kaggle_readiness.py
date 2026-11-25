"""Static Kaggle readiness checks for the Mission 02.2 baseline.

This script never executes the notebook, never loads a model and never touches
the GPU. It only parses the notebook JSON, the YAML config, the datasets and
the local scripts, then prints a readiness report.

Usage:
    python benchmark/scripts/verify_kaggle_readiness.py
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required. Use the project environment, for example:\n"
        r"  C:\LF\DLP\.venv-benchmark\Scripts\python.exe "
        r"benchmark\scripts\verify_kaggle_readiness.py"
    )
    raise SystemExit(1)

TASKS = [
    "code_generation",
    "code_explanation",
    "bug_detection",
    "code_refactoring",
    "unit_test_generation",
    "code_completion",
]

FORBIDDEN_CODE = [
    "google.colab",
    "drive.mount",
    "files.download",
    "import subprocess",
    "subprocess.run",
    "import tempfile",
]

REQUIRED_NOTEBOOK = [
    'INPUT_ROOT = "/kaggle/input"',
    'RESULTS_ROOT = os.path.join(WORKDIR, "results")',
    'CHECKPOINTS_ROOT = RESULTS_ROOT',
    'MODE = "full"',
    '"smoke_test"',
    'DEVICE_MAP = {"": 0} if SINGLE_GPU else "auto"',
    'EXECUTION_BACKEND = "none"',
    "ALLOW_UNSANDBOXED_CODE_EXECUTION = False",
    "TASKS_REQUIRING_EXECUTION",
    "MAX_INPUT_TOKENS = 8192",
    "def run_python",
    "raise RuntimeError",
    "def _static_syntax_ok",
    "ast.parse",
    "RUN_IDS",
    "INPUT_IS_READ_ONLY",
    "RESULTS_MODE_DIR",
    "write_sha256sums",
]


def dig(mapping, dotted, default=None):
    current = mapping
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    benchmark = root / "benchmark"
    notebook_path = benchmark / "notebooks" / "baseline_benchmark.ipynb"
    config_path = benchmark / "configs" / "baseline_config.yaml"

    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def warn(condition: bool, message: str) -> None:
        if not condition:
            warnings.append(message)

    # ------------------------------------------------------------------ notebook
    check(notebook_path.is_file(), f"Notebook missing: {notebook_path}")
    if notebook_path.is_file():
        nb = json.loads(notebook_path.read_text(encoding="utf-8"))
        cells = nb.get("cells", [])
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        check(len(cells) >= 20, f"Notebook has too few cells: {len(cells)}")
        check(len(code_cells) >= 10, f"Notebook has too few code cells: {len(code_cells)}")
        code_sources = []
        for index, cell in enumerate(code_cells):
            source = "".join(cell.get("source", []))
            code_sources.append(source)
            check(cell.get("execution_count") is None,
                  f"Code cell {index} has a non-null execution_count")
            check(not cell.get("outputs"),
                  f"Code cell {index} contains saved outputs")
            try:
                ast.parse(source)
            except SyntaxError as exc:
                errors.append(f"Code cell {index} does not parse: {exc}")
        all_code = "\n".join(code_sources)
        for needle in FORBIDDEN_CODE:
            check(needle not in all_code, f"Forbidden code pattern in notebook: {needle!r}")
        for needle in REQUIRED_NOTEBOOK:
            check(needle in all_code, f"Required notebook pattern missing: {needle!r}")
        check(all_code.count("run_python(") == 1,
              "run_python() must only be defined, never called")
        check("compile(" not in all_code,
              "Notebook must not compile generated code (use ast.parse only)")
        check("exec(" not in all_code,
              "Notebook must not exec generated code")
        notes.append(f"Notebook: {len(cells)} cells, {len(code_cells)} code cells, all parse")

    # -------------------------------------------------------------------- config
    check(config_path.is_file(), f"Config missing: {config_path}")
    config = {}
    if config_path.is_file():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        check(dig(config, "experiment.platform") == "kaggle", "platform must be kaggle")
        check(dig(config, "experiment.precision") == "fp16", "precision must be fp16")
        check(dig(config, "experiment.single_gpu") is True, "single_gpu must be true")
        check(dig(config, "experiment.device_map") == {"": 0}, "device_map must be {'': 0}")
        check(dig(config, "experiment.max_input_tokens") == 8192, "max_input_tokens must be 8192")
        check(dig(config, "platform_paths.kaggle.input_root") == "/kaggle/input",
              "input_root must be /kaggle/input")
        check(dig(config, "platform_paths.kaggle.workdir") == "/kaggle/working",
              "workdir must be /kaggle/working")
        check(dig(config, "platform_paths.kaggle.results_root") == "/kaggle/working/results",
              "results_root must be /kaggle/working/results")
        check(dig(config, "modes.full.results_subdir") == "baseline",
              "MODE=full must write to baseline/")
        check(dig(config, "modes.smoke_test.results_subdir") == "smoke_test",
              "MODE=smoke_test must write to smoke_test/")
        check(dig(config, "runs.mode") == "full", "runs.mode must be full")
        check(dig(config, "security.execution_backend") == "none",
              "execution_backend must be none")
        check(dig(config, "security.allow_unsandboxed_code_execution") is False,
              "allow_unsandboxed_code_execution must be false")
        forbidden = dig(config, "platform_paths.forbidden", [])
        check(any("Google Drive" in item for item in forbidden), "Google Drive must be forbidden")
        check(any("Colab" in item for item in forbidden), "Colab must be forbidden")
        model_ids = [m.get("id") for m in config.get("models", [])]
        check(len(model_ids) == 3, "Exactly three models are expected")
        for model in config.get("models", []):
            peak = model.get("worst_case_peak_vram_gb", model.get("expected_peak_vram_gb"))
            check(peak is not None and peak <= 15.0,
                  f"{model.get('id')}: static peak {peak} GB exceeds the T4 budget")
            check(model.get("verification_status") == "static_estimate_not_loaded",
                  f"{model.get('id')}: verification status must be static_estimate_not_loaded")
        notes.append("Config: Kaggle-only paths, full/smoke modes, single GPU, execution disabled")

    # ------------------------------------------------------------------- data
    dataset_rows: dict[str, int] = {}
    for task in TASKS:
        test_path = benchmark / "datasets" / "test" / f"{task}.jsonl"
        private_path = benchmark / "datasets" / "private" / "test" / f"{task}.jsonl"
        check(test_path.is_file(), f"Missing test file: {test_path}")
        check(private_path.is_file(), f"Missing private test file: {private_path}")
        if not test_path.is_file() or not private_path.is_file():
            continue
        test_rows = [json.loads(line) for line in test_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        private_rows = [json.loads(line) for line in private_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        dataset_rows[task] = len(test_rows)
        check(len(test_rows) > 0, f"{task}: empty test split")
        check({r.get("id") for r in test_rows} == {r.get("id") for r in private_rows},
              f"{task}: test/private IDs differ")
        # The public split keeps private keys as placeholders (None/"None"),
        # never as actual references. Only non-empty values are a leak.
        private_keys = {"reference_tests", "expected_output", "private_artifacts"}
        empty_values = {None, "", "None", "null", "{}", "[]"}
        for row in test_rows:
            bad = [
                key for key in private_keys
                if key in row and row[key] not in empty_values
            ]
            if bad:
                errors.append(f"{task}: model-facing test row {row.get('id')} leaks {sorted(bad)}")
                break
    check(sum(dataset_rows.values()) == 670,
          f"Expected 670 test examples, found {sum(dataset_rows.values())}")
    check((benchmark / "prompts" / "prompt_registry.py").is_file(),
          "prompt_registry.py is missing")
    notes.append("Data: " + ", ".join(f"{k}={v}" for k, v in dataset_rows.items())
                 + f", total={sum(dataset_rows.values())}")

    # ----------------------------------------------------------------- scripts
    for name in [
        "merge_results.py",
        "validate_baseline_results.py",
        "aggregate_baseline.py",
        "prepare_kaggle_dataset.py",
        "verify_kaggle_readiness.py",
    ]:
        path = benchmark / "scripts" / name
        check(path.is_file(), f"Missing script: {path}")
        if path.is_file():
            try:
                ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                errors.append(f"{name} does not parse: {exc}")

    # --------------------------------------------------------------- local bundle
    bundle = root / "kaggle_upload" / "slm-benchmark-baseline"
    if bundle.is_dir():
        metadata_path = bundle / "dataset-metadata.json"
        example_path = bundle / "dataset-metadata.example.json"
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            check(metadata.get("isPrivate") is True, "Bundle dataset must be private")
            check("<KAGGLE_USERNAME>" not in metadata.get("id", ""),
                  "Bundle dataset-metadata.json still has the placeholder owner")
        elif example_path.is_file():
            warnings.append(
                "Bundle has dataset-metadata.example.json only; rerun "
                "prepare_kaggle_dataset.py --owner <username> --force before "
                "using the Kaggle CLI (the web UI upload does not need it)."
            )
        else:
            errors.append("Bundle has neither dataset-metadata.json nor dataset-metadata.example.json")
        check((bundle / "benchmark" / "datasets" / "test").is_dir(),
              "Bundle is missing benchmark/datasets/test")
        check((bundle / "benchmark" / "datasets" / "private" / "test").is_dir(),
              "Bundle is missing benchmark/datasets/private/test")
        forbidden_suffixes = {".safetensors", ".bin", ".pt", ".pth", ".gguf"}
        weights = [p for p in bundle.rglob("*") if p.is_file() and p.suffix.lower() in forbidden_suffixes]
        check(not weights, f"Bundle contains model weights: {[str(p) for p in weights[:3]]}")
        notes.append(f"Bundle: {bundle} (private local upload staging folder)")
    else:
        warnings.append("Local Kaggle bundle not found; run prepare_kaggle_dataset.py --owner <username>")

    # ------------------------------------------------------------------ report
    print("Kaggle readiness report")
    print("=" * 60)
    for note in notes:
        print("OK  ", note)
    for warning in warnings:
        print("WARN", warning)
    for error in errors:
        print("FAIL", error)
    print("=" * 60)
    if errors:
        print(f"RESULT: FAIL ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    print(f"RESULT: PASS ({len(warnings)} warning(s))")
    print("No notebook was executed, no model was loaded and no GPU was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
