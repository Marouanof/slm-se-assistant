"""Rebuild the pilot SFT data so it matches the evaluation harness.

The first SFT run under-performed because the training data used a different
prompt format than the benchmark harness and because every completion ended
with a stray ``|`` before the end-of-text token. This script rewrites the
pilot rows into the exact ``SYSTEM_PROMPTS`` / ``USER_TEMPLATES`` used at
evaluation time and normalises the completions.

It performs no tokenisation: ``system``/``user``/``completion`` are stored as
plain strings so the training notebook can call the tokenizer's own
``apply_chat_template`` and therefore match inference byte-for-byte.

Usage:
    python build_sft_v2.py --input-dir <pilot_dir> --output-dir <out_dir>
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prompts.prompt_registry import SYSTEM_PROMPTS, USER_TEMPLATES  # noqa: E402

_USER_RE = re.compile(r"<\|user\|>(.*?)<\|end\|>", re.DOTALL)


def strip_pilot_completion(completion: str) -> str:
    """Remove the end-of-text token and the stray pipe the pilot data appends."""
    completion = completion.replace("<|endoftext|>", "")
    completion = completion.replace("<|end|>", "")
    completion = completion.rstrip()
    if completion.endswith("|"):
        completion = completion[:-1]
    return completion.rstrip()


def extract_user_content(prompt: str) -> str:
    match = _USER_RE.search(prompt)
    if not match:
        raise ValueError("no <|user|> block in pilot prompt")
    return match.group(1)


def split_preface(user_content: str) -> tuple[str, str]:
    """The pilot user turn is '<preface>\n\n<payload>'. Return both."""
    if "\n\n" not in user_content:
        return "", user_content
    preface, payload = user_content.split("\n\n", 1)
    return preface, payload


def _signature_line(code: str) -> str | None:
    match = re.search(r"^def\s+\w+\s*\([^)]*\)\s*(?:->\s*[^:\n]+)?:", code, re.MULTILINE)
    return match.group(0) if match else None


def build_code_generation_input(code: str, task_text: str) -> str | None:
    """Turn an MBPP solution into a HumanEval-style stub (imports + signature)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(funcs) != 1:
        return None
    signature = _signature_line(code)
    if not signature:
        return None
    imports = [
        ast.unparse(node)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    doc = task_text.strip().replace('"""', "'''")
    parts = []
    if imports:
        parts.append("\n".join(imports))
        parts.append("")
    parts.append(signature)
    parts.append(f'    """{doc}"""')
    parts.append("    ")
    return "\n".join(parts)


def build_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    out: list[dict] = []
    stats = {"total": 0, "kept": 0, "skipped_cg": 0, "by_task": {}}
    for row in rows:
        stats["total"] += 1
        task = row["task"]
        if task not in SYSTEM_PROMPTS:
            continue
        completion = strip_pilot_completion(row["completion"])
        user_content = extract_user_content(row["prompt"])
        _preface, payload = split_preface(user_content)

        if task == "code_generation":
            stub = build_code_generation_input(completion, payload)
            if stub is None:
                stats["skipped_cg"] += 1
                continue
            input_content = stub
            completion = f"```python\n{completion.strip()}\n```"
        elif task == "unit_test_generation":
            input_content = payload
            completion = f"```python\n{completion.strip()}\n```"
        elif task == "code_completion":
            input_content = payload
        else:
            continue

        user = USER_TEMPLATES[task].format(input=input_content)
        out.append(
            {
                "task": task,
                "system": SYSTEM_PROMPTS[task],
                "user": user,
                "completion": completion,
                "source_hash": row.get("source_hash"),
            }
        )
        stats["kept"] += 1
        stats["by_task"][task] = stats["by_task"].get(task, 0) + 1
    return out, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        default=r"C:\Users\merou\AppData\Local\Temp\opencode\pilot",
    )
    parser.add_argument(
        "--output-dir",
        default=r"C:\Users\merou\AppData\Local\Temp\opencode\sft_v2",
    )
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for split, name in [
        ("train", "sft_pilot_train_formatted.jsonl"),
        ("validation", "sft_pilot_validation_formatted.jsonl"),
    ]:
        rows = [
            json.loads(line)
            for line in (in_dir / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        built, stats = build_rows(rows)
        dest = out_dir / f"sft_v2_{split}.jsonl"
        with dest.open("w", encoding="utf-8") as handle:
            for item in built:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"{split}: {stats['kept']}/{stats['total']} kept -> {dest}")
        print(f"  by_task={stats['by_task']} skipped_code_generation={stats['skipped_cg']}")

    # Preview one record per task from the train split.
    preview = [
        json.loads(line)
        for line in (out_dir / "sft_v2_train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seen = set()
    for row in preview:
        if row["task"] in seen:
            continue
        seen.add(row["task"])
        print("\n" + "=" * 78)
        print("TASK:", row["task"])
        print("--- SYSTEM ---")
        print(row["system"])
        print("--- USER ---")
        print(row["user"][:900])
        print("--- COMPLETION ---")
        print(row["completion"][:700])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
