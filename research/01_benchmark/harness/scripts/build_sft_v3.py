"""Build the six-task SFT v3 dataset.

The v2 dataset only covered code_generation, unit_test_generation and
code_completion.  This builder keeps those rows (re-formatted by
``build_sft_v2``), adds the three missing tasks from public training splits,
and writes a balanced validation set plus a reproducibility manifest.

Sources
-------
* MBPP full train + validation (via the existing pilot file): the pilot
  already excludes every MBPP+ test id used by the benchmark.
* CodeXGLUE defect detection train/validation: C functions with a binary
  defect label.
* CodeXGLUE code-to-text Python validation: Python functions with a
  docstring.  The validation split is used instead of the 291 MB train split
  to keep the download small.  It is disjoint from the benchmark's test split.

No benchmark test or private reference is written to the output.  If the
private test files are available, they are read only to compute normalised
hashes and reject exact overlaps.

Usage
-----
    python build_sft_v3.py \
        --pilot-dir C:/Users/merou/AppData/Local/Temp/opencode/pilot \
        --codexglue-dir C:/Users/merou/AppData/Local/Temp/opencode/codexglue \
        --output-dir C:/Users/merou/AppData/Local/Temp/opencode/sft_v3
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import os
import random
import re
import sys
import urllib.request
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prompts.prompt_registry import SYSTEM_PROMPTS, USER_TEMPLATES  # noqa: E402

from build_sft_v2 import (  # noqa: E402
    build_code_generation_input,
    extract_user_content,
    split_preface,
    strip_pilot_completion,
)

SEED = 42
BUILDER_VERSION = "sft-v3.0"

CODEXGLUE_URLS = {
    "defect_train.parquet": (
        "https://huggingface.co/datasets/google/code_x_glue_cc_defect_detection/"
        "resolve/main/data/train-00000-of-00001.parquet"
    ),
    "defect_validation.parquet": (
        "https://huggingface.co/datasets/google/code_x_glue_cc_defect_detection/"
        "resolve/main/data/validation-00000-of-00001.parquet"
    ),
    "code2text_py_validation.parquet": (
        "https://huggingface.co/datasets/google/code_x_glue_ct_code_to_text/"
        "resolve/main/python/validation-00000-of-00001.parquet"
    ),
}

TASKS = [
    "code_generation",
    "code_explanation",
    "bug_detection",
    "code_refactoring",
    "unit_test_generation",
    "code_completion",
]

# Generous character limits.  The training notebook truncates at 2048 tokens;
# these limits keep the prompt + completion well below that on the Qwen tokenizer.
MAX_BUG_CHARS = 6000
MAX_EXPLANATION_CODE_CHARS = 5000
MAX_EXPLANATION_DOC_CHARS = 1500
MAX_CG_AUX_CODE_CHARS = 3000

_REFACTOR_CHANGES = (
    "### Changes\n"
    "- Preserved the public signature and return values.\n"
    "- Kept the existing control flow and edge-case behaviour.\n"
    "- Improved readability without changing observable behaviour."
)

_TYPING_NAMES = {
    "List", "Dict", "Tuple", "Set", "Optional", "Any", "Union", "Callable",
    "Iterable", "Sequence", "Mapping", "Iterator", "Generator", "Type",
    "TypeVar", "Generic", "Protocol", "Literal", "Final", "ClassVar",
    "NoReturn", "overload",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def text_hash(text: str) -> str:
    return sha256_text(normalise_ws(text))


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name} ({dest.stat().st_size / 1_000_000:.2f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {dest.name}")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    print(f"  -> {dest.stat().st_size / 1_000_000:.2f} MB")


def ensure_codexglue_sources(source_dir: Path, allow_download: bool) -> dict[str, Path]:
    source_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, url in CODEXGLUE_URLS.items():
        dest = source_dir / name
        if not dest.exists() and allow_download:
            download_file(url, dest)
        if not dest.exists():
            raise FileNotFoundError(
                f"{dest} is missing; rerun with --download or place the parquet file there"
            )
        paths[name] = dest
    return paths


def read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            "pyarrow is required to read CodeXGLUE parquet files. "
            "Install it with: python -m pip install pyarrow"
        ) from exc
    return pq.read_table(path).to_pylist()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_row(
    task: str,
    input_content: str,
    completion: str,
    *,
    source: str,
    source_id: str,
    license_name: str | None,
    source_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "task": task,
        "system": SYSTEM_PROMPTS[task],
        "user": USER_TEMPLATES[task].format(input=input_content),
        # Kept for the leakage audit and for debugging; the training notebook
        # only reads system/user/completion.
        "input": input_content,
        "completion": completion,
        "source": source,
        "source_id": source_id,
        "license": license_name,
        "source_hash": source_hash,
    }


def is_single_function(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    return len(funcs) == 1


def function_node(code: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(funcs) != 1:
        return None
    return funcs[0]


def local_names(node: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
        names.add(arg.arg)
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            names.add(child.name)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            for alias in child.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def external_loads(node: ast.FunctionDef) -> set[str]:
    allowed = set(dir(builtins)) | local_names(node) | _TYPING_NAMES
    allowed |= {"__name__", "__file__", "__doc__"}
    used: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            used.add(child.id)
    return used - allowed


def strip_docstring(code: str) -> str | None:
    """Replace the first triple-quoted string with ``pass``, as the harness does."""
    match = re.search(
        r'(?m)^([ \t]*)(?:[rRuUbB]{0,2})("""|\'\'\')(.*?)\2',
        code,
        re.DOTALL,
    )
    if not match:
        return None
    indent = match.group(1)
    return code[: match.start()] + indent + "pass" + code[match.end() :]


def explanation_completion(docstring: str) -> str:
    doc = docstring.strip()
    return (
        f"## Purpose\n{doc}\n"
        "## Parameters\nNot applicable.\n"
        "## Return value\nNot applicable.\n"
        "## Complexity\nNot determinable from the snippet."
    )


def bug_completion(has_bug: bool) -> str:
    if has_bug:
        payload = {
            "has_bug": True,
            "location": "function",
            "description": "The function contains a defect.",
            "fix": "Correct the defective logic in the function.",
        }
    else:
        payload = {
            "has_bug": False,
            "location": "",
            "description": "No defect detected in the provided function.",
            "fix": "",
        }
    return json.dumps(payload, ensure_ascii=False)


def build_refactoring_row(pilot_row: dict[str, Any], split: str) -> dict[str, Any] | None:
    completion = strip_pilot_completion(pilot_row["completion"])
    if not is_single_function(completion):
        return None
    _preface, payload = split_preface(extract_user_content(pilot_row["prompt"]))
    task_text = payload.strip()
    input_content = f"# {task_text}\n{completion.strip()}"
    target = f"```python\n{completion.strip()}\n```\n\n{_REFACTOR_CHANGES}"
    return make_row(
        "code_refactoring",
        input_content,
        target,
        source="mbpp",
        source_id=str(pilot_row.get("example_id")),
        license_name=pilot_row.get("license"),
        source_hash=pilot_row.get("source_hash"),
    )


def build_pilot_rows(pilot_dir: Path, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    train_raw = read_jsonl(pilot_dir / "sft_pilot_train_formatted.jsonl")
    val_raw = read_jsonl(pilot_dir / "sft_pilot_validation_formatted.jsonl")

    # Keep the pilot's own validation split, then hold out 20 train rows for
    # each task so every task has 50 validation examples and the eval loss is
    # not dominated by one task.
    #
    # code_refactoring is derived from code_generation rows. The 20 rows held
    # out for refactoring validation are removed from both code_generation and
    # refactoring training, so no row is in train and validation at once.
    rng = random.Random(seed)
    by_task_train: dict[str, list[dict[str, Any]]] = {task: [] for task in TASKS}
    for row in train_raw:
        by_task_train[row["task"]].append(row)

    moved: dict[str, list[dict[str, Any]]] = {}
    for task in ["unit_test_generation", "code_completion"]:
        candidates = list(by_task_train[task])
        rng.shuffle(candidates)
        moved[task] = candidates[:20]
        by_task_train[task] = candidates[20:]

    cg_candidates = list(by_task_train["code_generation"])
    rng.shuffle(cg_candidates)
    moved["code_refactoring"] = cg_candidates[:20]
    by_task_train["code_generation"] = cg_candidates[20:]

    train_rows: list[dict[str, Any]] = []
    val_rows: list[dict[str, Any]] = []

    def convert(row: dict[str, Any]) -> dict[str, Any] | None:
        task = row["task"]
        completion = strip_pilot_completion(row["completion"])
        _preface, payload = split_preface(extract_user_content(row["prompt"]))
        if task == "code_generation":
            stub = build_code_generation_input(completion, payload)
            if stub is None:
                return None
            return make_row(
                task,
                stub,
                f"```python\n{completion.strip()}\n```",
                source="mbpp",
                source_id=str(row.get("example_id")),
                license_name=row.get("license"),
                source_hash=row.get("source_hash"),
            )
        if task == "unit_test_generation":
            return make_row(
                task,
                payload,
                f"```python\n{completion.strip()}\n```",
                source="mbpp",
                source_id=str(row.get("example_id")),
                license_name=row.get("license"),
                source_hash=row.get("source_hash"),
            )
        if task == "code_completion":
            return make_row(
                task,
                payload,
                completion,
                source="mbpp",
                source_id=str(row.get("example_id")),
                license_name=row.get("license"),
                source_hash=row.get("source_hash"),
            )
        if task == "code_refactoring":
            return build_refactoring_row(row, "train")
        return None

    for task in ["code_generation", "unit_test_generation", "code_completion"]:
        for row in by_task_train[task]:
            built = convert(row)
            if built is not None:
                train_rows.append(built)

    # Refactoring is built from the same MBPP code-generation rows.  The 20
    # moved rows are appended to validation; the remaining rows are train.
    for row in by_task_train["code_generation"]:
        built = build_refactoring_row(row, "train")
        if built is not None:
            train_rows.append(built)

    for row in val_raw:
        if row["task"] in {"code_generation", "unit_test_generation", "code_completion"}:
            built = convert(row)
            if built is not None:
                val_rows.append(built)
            # The pilot validation code-generation rows also serve as
            # refactoring validation rows (same function, different task).
            if row["task"] == "code_generation":
                refactored = build_refactoring_row(row, "validation")
                if refactored is not None:
                    val_rows.append(refactored)
        elif row["task"] == "code_refactoring":
            built = build_refactoring_row(row, "validation")
            if built is not None:
                val_rows.append(built)

    for task, rows in moved.items():
        for row in rows:
            built = build_refactoring_row(row, "validation") if task == "code_refactoring" else convert(row)
            if built is not None:
                val_rows.append(built)

    stats = {
        "pilot_train_input": len(train_raw),
        "pilot_validation_input": len(val_raw),
        "moved_to_validation": {task: len(rows) for task, rows in moved.items()},
    }
    return train_rows, val_rows, stats


def benchmark_hashes(public_test_dir: Path, private_test_dir: Path) -> dict[str, set[str]]:
    """Return normalised hashes of the benchmark test inputs/references.

    The hashes are used only to reject exact train/test overlaps.  No test row
    is written to the SFT files.
    """
    hashes: dict[str, set[str]] = {
        "bug_code": set(),
        "explanation_code": set(),
        "explanation_doc": set(),
        "generation_code": set(),
        "generation_body": set(),
    }
    public = public_test_dir
    private = private_test_dir

    bug_public = public / "bug_detection.jsonl"
    if bug_public.exists():
        for row in read_jsonl(bug_public):
            hashes["bug_code"].add(text_hash(row.get("input", "")))
    bug_private = private / "bug_detection.jsonl"
    if bug_private.exists():
        for row in read_jsonl(bug_private):
            artifacts = row.get("private_artifacts") or {}
            hashes["bug_code"].add(text_hash(artifacts.get("original_code", "")))

    explanation_private = private / "code_explanation.jsonl"
    if explanation_private.exists():
        for row in read_jsonl(explanation_private):
            artifacts = row.get("private_artifacts") or {}
            hashes["explanation_code"].add(text_hash(artifacts.get("original_code", "")))
            hashes["explanation_doc"].add(text_hash(row.get("expected_output", "")))
    explanation_public = public / "code_explanation.jsonl"
    if explanation_public.exists():
        for row in read_jsonl(explanation_public):
            # The public input is the docstring-stripped code, which is what
            # the SFT code_explanation prompt uses.
            hashes["explanation_code"].add(text_hash(row.get("input", "")))

    generation_private = private / "code_generation.jsonl"
    if generation_private.exists():
        for row in read_jsonl(generation_private):
            hashes["generation_body"].add(text_hash(row.get("expected_output", "")))
    generation_public = public / "code_generation.jsonl"
    if generation_public.exists():
        for row in read_jsonl(generation_public):
            hashes["generation_code"].add(text_hash(row.get("input", "")))

    return hashes


def mbpp_benchmark_ids(public_test_dir: Path) -> set[int]:
    ids: set[int] = set()
    for task in ["code_generation", "code_refactoring", "unit_test_generation", "code_completion"]:
        path = public_test_dir / f"{task}.jsonl"
        if not path.exists():
            continue
        for row in read_jsonl(path):
            match = re.search(r"mbpp_plus__(\d+)", row.get("id", ""))
            if match:
                ids.add(int(match.group(1)))
    return ids


def filter_mbpp_leakage(rows: list[dict[str, Any]], benchmark_ids: set[int]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        match = re.search(r"__mbpp__(\d+)", str(row.get("source_id", "")))
        if match and int(match.group(1)) in benchmark_ids:
            dropped += 1
            continue
        kept.append(row)
    return kept, dropped


def select_balanced(rows: list[dict[str, Any]], target: bool, count: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = [row for row in rows if bool(row["target"]) is target]
    rng.shuffle(pool)
    return pool[:count]


def build_bug_rows(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    hashes: dict[str, set[str]],
    seed: int,
    n_train: int,
    n_val: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed + 1)

    def usable(row: dict[str, Any]) -> bool:
        code = row.get("func") or ""
        return bool(code.strip()) and len(code) <= MAX_BUG_CHARS and text_hash(code) not in hashes["bug_code"]

    train_pool = [row for row in train_rows if usable(row)]
    val_pool = [row for row in val_rows if usable(row)]
    train_selected = select_balanced(train_pool, True, n_train // 2, rng) + select_balanced(train_pool, False, n_train // 2, rng)
    val_selected = select_balanced(val_pool, True, n_val // 2, rng) + select_balanced(val_pool, False, n_val // 2, rng)
    rng.shuffle(train_selected)
    rng.shuffle(val_selected)

    def convert(row: dict[str, Any], split: str) -> dict[str, Any]:
        return make_row(
            "bug_detection",
            row["func"],
            bug_completion(bool(row["target"])),
            source=f"code_x_glue_cc_defect_detection_{split}",
            source_id=str(row.get("id")),
            license_name="C-UDA",
        )

    built_train = [convert(row, "train") for row in train_selected]
    built_val = [convert(row, "validation") for row in val_selected]
    stats = {
        "train_pool": len(train_pool),
        "val_pool": len(val_pool),
        "train_selected": len(built_train),
        "val_selected": len(built_val),
        "train_label_counts": dict(Counter(bool(row["target"]) for row in train_selected)),
        "val_label_counts": dict(Counter(bool(row["target"]) for row in val_selected)),
    }
    return built_train, built_val, stats


def build_code2text_rows(
    rows: list[dict[str, Any]],
    hashes: dict[str, set[str]],
    seed: int,
    n_explanation_train: int,
    n_explanation_val: int,
    n_cg_train: int,
    n_cg_val: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed + 2)
    seen: set[str] = set()
    explanation_candidates: list[dict[str, Any]] = []
    cg_candidates: list[dict[str, Any]] = []

    for row in rows:
        code = row.get("code") or ""
        doc = (row.get("docstring") or "").strip()
        if not doc or len(code) > MAX_EXPLANATION_CODE_CHARS or len(doc) > MAX_EXPLANATION_DOC_CHARS:
            continue
        code_hash = text_hash(code)
        if code_hash in seen:
            continue
        seen.add(code_hash)
        if code_hash in hashes["explanation_code"] or text_hash(doc) in hashes["explanation_doc"]:
            continue
        node = function_node(code)
        if node is None or node.decorator_list:
            continue
        if node.args.args and node.args.args[0].arg in {"self", "cls"}:
            continue
        stripped = strip_docstring(code)
        if stripped is None:
            continue
        try:
            ast.parse(stripped)
        except SyntaxError:
            continue
        item = {
            "row": row,
            "code_hash": code_hash,
            "stripped": stripped,
            "doc": doc,
        }
        explanation_candidates.append(item)
        if len(code) <= MAX_CG_AUX_CODE_CHARS and not external_loads(node):
            cg_candidates.append(item)

    rng.shuffle(explanation_candidates)
    rng.shuffle(cg_candidates)
    explanation_selected = explanation_candidates[: n_explanation_train + n_explanation_val]
    cg_selected = cg_candidates[: n_cg_train + n_cg_val]

    def explanation_row(item: dict[str, Any]) -> dict[str, Any]:
        row = item["row"]
        return make_row(
            "code_explanation",
            item["stripped"],
            explanation_completion(item["doc"]),
            source="code_x_glue_ct_code_to_text_python_validation",
            source_id=str(row.get("id")),
            license_name="C-UDA",
        )

    def cg_row(item: dict[str, Any]) -> dict[str, Any] | None:
        row = item["row"]
        stub = build_code_generation_input(row["code"], item["doc"])
        if stub is None:
            return None
        return make_row(
            "code_generation",
            stub,
            f"```python\n{row['code'].strip()}\n```",
            source="code_x_glue_ct_code_to_text_python_validation",
            source_id=str(row.get("id")),
            license_name="C-UDA",
        )

    explanation_train = [explanation_row(item) for item in explanation_selected[:n_explanation_train]]
    explanation_val = [explanation_row(item) for item in explanation_selected[n_explanation_train:]]
    cg_train = [built for item in cg_selected[:n_cg_train] if (built := cg_row(item)) is not None]
    cg_val = [built for item in cg_selected[n_cg_train:] if (built := cg_row(item)) is not None]

    stats = {
        "explanation_candidates": len(explanation_candidates),
        "code_generation_candidates": len(cg_candidates),
        "explanation_train": len(explanation_train),
        "explanation_val": len(explanation_val),
        "code_generation_aux_train": len(cg_train),
        "code_generation_aux_val": len(cg_val),
        "code_generation_aux_overlaps_explanation": len(
            {item["row"].get("id") for item in cg_selected}
            & {item["row"].get("id") for item in explanation_selected}
        ),
    }
    return explanation_train + cg_train, explanation_val + cg_val, stats


def count_by_task(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(row["task"] for row in rows).items()))


def build_manifest(
    args: argparse.Namespace,
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    pilot_stats: dict[str, Any],
    bug_stats: dict[str, Any],
    code2text_stats: dict[str, Any],
    leakage: dict[str, Any],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    return {
        "builder": BUILDER_VERSION,
        "created_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "seed": args.seed,
        "tasks": TASKS,
        "counts": {
            "train": count_by_task(train_rows),
            "validation": count_by_task(val_rows),
            "train_total": len(train_rows),
            "validation_total": len(val_rows),
        },
        "sources": {
            "mbpp": {
                "description": "MBPP full train+validation, via the v2 pilot file; benchmark MBPP+ ids excluded",
                "license": "CC-BY-4.0",
            },
            "code_x_glue_cc_defect_detection": {
                "description": "CodeXGLUE defect detection train/validation",
                "license": "C-UDA",
            },
            "code_x_glue_ct_code_to_text_python_validation": {
                "description": "CodeXGLUE code-to-text Python validation; used for explanation and a small code-generation replay set",
                "license": "C-UDA",
            },
        },
        "source_files_sha256": source_hashes,
        "pilot": pilot_stats,
        "bug_detection": bug_stats,
        "code_to_text": code2text_stats,
        "leakage_check": leakage,
        "output_files_sha256": {
            "sft_v3_train.jsonl": sha256_file(Path(args.output_dir) / "sft_v3_train.jsonl"),
            "sft_v3_validation.jsonl": sha256_file(Path(args.output_dir) / "sft_v3_validation.jsonl"),
        },
        "notes": [
            "No benchmark test or private reference is included in the SFT files.",
            "bug_detection descriptions/locations/fixes are templated; only has_bug is supervised.",
            "code_refactoring targets are the original MBPP functions (identity refactors) used to teach the output contract.",
            "code_explanation targets wrap the CodeXGLUE docstring in the four required headings; content quality is limited by the docstring.",
            "The code-generation replay set comes from real repository functions, not algorithmic benchmark items.",
        ],
    }


def write_readme(output_dir: Path, manifest: dict[str, Any]) -> None:
    counts = manifest["counts"]
    lines = [
        "# SLM SFT v3 dataset",
        "",
        "Six-task SFT data built by `research/01_benchmark/harness/scripts/build_sft_v3.py`.",
        "",
        "## Counts",
        "",
        f"- Train: {counts['train_total']}",
        f"- Validation: {counts['validation_total']}",
        "",
        "| Task | Train | Validation |",
        "|---|---:|---:|",
    ]
    for task in TASKS:
        lines.append(f"| {task} | {counts['train'].get(task, 0)} | {counts['validation'].get(task, 0)} |")
    lines += [
        "",
        "## Sources",
        "",
        "- MBPP full train+validation, via the v2 pilot file (CC-BY-4.0). The pilot excludes every MBPP+ test id used by the benchmark.",
        "- CodeXGLUE defect detection train/validation (C-UDA).",
        "- CodeXGLUE code-to-text Python **validation** (C-UDA), chosen over the 291 MB train split to keep the download small.",
        "",
        "## What is supervised",
        "",
        "- `code_generation`: complete function, fenced, from MBPP plus a small real-repository replay set.",
        "- `unit_test_generation`: pytest suite, fenced.",
        "- `code_completion`: raw next line(s).",
        "- `code_refactoring`: original function + `### Changes`; this teaches the output contract, not a semantic rewrite.",
        "- `bug_detection`: JSON object. The `description`/`location`/`fix` strings are templated; only `has_bug` is a real label.",
        "- `code_explanation`: the four required headings with the CodeXGLUE docstring under `## Purpose`; the other sections are deliberately short.",
        "",
        "## Leakage",
        "",
        f"- Benchmark MBPP+ ids excluded from the pilot: {manifest['leakage_check'].get('mbpp_ids_dropped', 0)}",
        f"- Exact CodeXGLUE/MBPP test overlaps found: {manifest['leakage_check'].get('exact_overlaps', 0)}",
        "- The private test files are read only to compute normalised hashes; they are never written to this dataset.",
        "",
        "## Regenerate",
        "",
        "```bash",
        "python research/01_benchmark/harness/scripts/build_sft_v3.py \\",
        "  --pilot-dir <pilot_dir> \\",
        "  --codexglue-dir <codexglue_dir> \\",
        "  --output-dir <out_dir>",
        "```",
        "",
        "Pass `--download` to fetch the three CodeXGLUE parquet files (~37 MB) when they are missing.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot-dir",
        default=r"C:\Users\merou\AppData\Local\Temp\opencode\pilot",
    )
    parser.add_argument(
        "--codexglue-dir",
        default=os.environ.get(
            "SLM_CODEXGLUE_DIR",
            r"C:\Users\merou\AppData\Local\Temp\opencode\codexglue",
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=r"C:\Users\merou\AppData\Local\Temp\opencode\sft_v3",
    )
    parser.add_argument(
        "--public-test-dir",
        default=str(Path(__file__).resolve().parents[1] / "datasets" / "test"),
    )
    parser.add_argument(
        "--private-test-dir",
        default=str(Path(__file__).resolve().parents[1] / "datasets" / "private" / "test"),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--download", action="store_true", help="Download missing CodeXGLUE parquet files")
    parser.add_argument("--bug-train", type=int, default=1200)
    parser.add_argument("--bug-val", type=int, default=50)
    parser.add_argument("--explanation-train", type=int, default=1200)
    parser.add_argument("--explanation-val", type=int, default=50)
    parser.add_argument("--cg-aux-train", type=int, default=500)
    parser.add_argument("--cg-aux-val", type=int, default=20)
    args = parser.parse_args()

    pilot_dir = Path(args.pilot_dir)
    codexglue_dir = Path(args.codexglue_dir)
    output_dir = Path(args.output_dir)
    public_test_dir = Path(args.public_test_dir)
    private_test_dir = Path(args.private_test_dir)

    if not (pilot_dir / "sft_pilot_train_formatted.jsonl").exists():
        raise SystemExit(f"pilot file not found under {pilot_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("== sources ==")
    source_paths = ensure_codexglue_sources(codexglue_dir, args.download)
    source_hashes = {path.name: sha256_file(path) for path in source_paths.values()}
    for name, digest in source_hashes.items():
        print(f"  {name}: {digest[:16]}...")

    print("== benchmark hashes ==")
    hashes = benchmark_hashes(public_test_dir, private_test_dir)
    print({key: len(value) for key, value in hashes.items()})
    benchmark_ids = mbpp_benchmark_ids(public_test_dir)

    print("== pilot ==")
    pilot_train, pilot_val, pilot_stats = build_pilot_rows(pilot_dir, args.seed)
    pilot_train, pilot_dropped = filter_mbpp_leakage(pilot_train, benchmark_ids)
    pilot_val, pilot_val_dropped = filter_mbpp_leakage(pilot_val, benchmark_ids)
    print("  train", count_by_task(pilot_train), "val", count_by_task(pilot_val))

    print("== bug detection ==")
    defect_train = read_parquet_rows(source_paths["defect_train.parquet"])
    defect_val = read_parquet_rows(source_paths["defect_validation.parquet"])
    bug_train, bug_val, bug_stats = build_bug_rows(
        defect_train,
        defect_val,
        hashes,
        args.seed,
        args.bug_train,
        args.bug_val,
    )
    print(" ", bug_stats)

    print("== code-to-text ==")
    code2text = read_parquet_rows(source_paths["code2text_py_validation.parquet"])
    c2t_train, c2t_val, c2t_stats = build_code2text_rows(
        code2text,
        hashes,
        args.seed,
        args.explanation_train,
        args.explanation_val,
        args.cg_aux_train,
        args.cg_aux_val,
    )
    print(" ", c2t_stats)

    train_rows = pilot_train + bug_train + c2t_train
    val_rows = pilot_val + bug_val + c2t_val

    # Final exact-overlap audit on the produced rows.  This catches accidental
    # duplicates that survived the source-level filters.
    def fenced_code(text: str) -> str:
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        return match.group(1) if match else text

    overlaps = 0
    for row in train_rows + val_rows:
        task = row["task"]
        if task == "bug_detection":
            if text_hash(row["input"]) in hashes["bug_code"]:
                overlaps += 1
        elif task == "code_explanation":
            if text_hash(row["input"]) in hashes["explanation_code"]:
                overlaps += 1
        elif task == "code_generation":
            code = fenced_code(row["completion"])
            if text_hash(code) in hashes["generation_body"] or text_hash(code) in hashes["generation_code"]:
                overlaps += 1
    if overlaps:
        raise SystemExit(f"refusing to write {overlaps} exact benchmark overlaps")

    write_jsonl(output_dir / "sft_v3_train.jsonl", train_rows)
    write_jsonl(output_dir / "sft_v3_validation.jsonl", val_rows)
    leakage = {
        "mbpp_ids_dropped": pilot_dropped + pilot_val_dropped,
        "exact_overlaps": overlaps,
        "private_test_available": (private_test_dir / "bug_detection.jsonl").exists(),
        "benchmark_mbpp_ids": len(benchmark_ids),
        "hash_sets": {key: len(value) for key, value in hashes.items()},
    }
    manifest = build_manifest(
        args,
        train_rows,
        val_rows,
        pilot_stats,
        bug_stats,
        c2t_stats,
        leakage,
        source_hashes,
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_readme(output_dir, manifest)
    (output_dir / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": "SLM SFT v3",
                "id": "merouanefaik/slm-sft-v3",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("== final ==")
    print("  train", count_by_task(train_rows), "total", len(train_rows))
    print("  val  ", count_by_task(val_rows), "total", len(val_rows))
    print("  wrote", output_dir)
    print("  train sha256", sha256_file(output_dir / "sft_v3_train.jsonl"))
    print("  val   sha256", sha256_file(output_dir / "sft_v3_validation.jsonl"))

    # Preview one row per task.
    seen = set()
    for row in train_rows:
        if row["task"] in seen:
            continue
        seen.add(row["task"])
        print("\n" + "=" * 78)
        print("TASK:", row["task"], "| source:", row["source"], "| id:", row["source_id"])
        print("--- USER (first 700) ---")
        print(row["user"][:700])
        print("--- COMPLETION (first 500) ---")
        print(row["completion"][:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
