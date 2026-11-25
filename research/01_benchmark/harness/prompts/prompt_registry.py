"""Provider-independent prompt registry for the six benchmark tasks.

The same textual messages are passed to every model. Model-specific chat
templates are applied only at the tokenizer boundary by ``apply_chat_template``;
the prompt content is never modified per model.

Executable example:
    python benchmark/prompts/prompt_registry.py --task code_generation --split test --index 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BENCHMARK_DIR = Path(__file__).resolve().parents[1]

SYSTEM_PROMPTS: dict[str, str] = {
    "code_generation": (
        "You are a senior Python software engineer. Solve the programming task by "
        "producing a complete, executable Python implementation. Do not include "
        "explanations, tests, examples or step-by-step reasoning."
    ),
    "code_explanation": (
        "You are a senior software engineer. Explain Python code accurately and "
        "concisely for a developer who can already read Python. Do not invent "
        "behaviour that is not supported by the code. Do not include step-by-step "
        "reasoning."
    ),
    "bug_detection": (
        "You are a senior C code reviewer. Decide whether the provided C function "
        "contains a defect. Base your answer only on the code. Do not include "
        "hidden reasoning or speculative issues that are not visible in the code."
    ),
    "code_refactoring": (
        "You are a senior Python software engineer. Refactor the supplied function "
        "without changing its observable behaviour. Preserve the public signature, "
        "return semantics and error behaviour. Do not add new third-party "
        "dependencies."
    ),
    "unit_test_generation": (
        "You are a senior Python test engineer. Write executable pytest tests for "
        "the supplied function. Cover normal, boundary and error cases. Do not use "
        "network access, external services or filesystem fixtures. Do not modify "
        "the function under test."
    ),
    "code_completion": (
        "You are a Python autocomplete engine. Complete the next line of the "
        "supplied code. Preserve the existing style and context. Do not repeat the "
        "supplied prefix. Do not add explanations."
    ),
}

USER_TEMPLATES: dict[str, str] = {
    "code_generation": (
        "Implement the following Python function. Return the complete function "
        "(signature included) in a single ```python fenced block. Do not include "
        "tests or explanations.\n\n"
        "```python\n{input}\n```"
    ),
    "code_explanation": (
        "Explain the following Python function. Use exactly these four Markdown "
        "sections, in this order:\n"
        "## Purpose\n"
        "## Parameters\n"
        "## Return value\n"
        "## Complexity\n\n"
        "If a section does not apply, write \"Not applicable\". State the time and "
        "space complexity in Big-O notation when it can be determined from the "
        "snippet; otherwise write \"Not determinable from the snippet\". Do not "
        "include the original code again.\n\n"
        "```python\n{input}\n```"
    ),
    "bug_detection": (
        "Review the following C function for a defect. Return exactly one JSON "
        "object with these keys:\n"
        '{{"has_bug": true or false, "location": "line or function, or empty string", '
        '"description": "short explanation", "fix": "short correction or empty string"}}\n\n'
        "Rules:\n"
        "- `has_bug` must be a JSON boolean.\n"
        "- Set `location` and `fix` to an empty string when `has_bug` is false.\n"
        "- Do not wrap the JSON in Markdown fences.\n"
        "- Return JSON only, with no prose before or after it.\n\n"
        "```c\n{input}\n```"
    ),
    "code_refactoring": (
        "Refactor the following Python function. Preserve its public signature, "
        "return values and observable behaviour. Return exactly two parts:\n"
        "1. A single ```python fenced block with the complete refactored function.\n"
        "2. A `### Changes` section with 1 to 5 bullet points describing the main "
        "changes.\n\n"
        "Do not change the function name and do not add new dependencies. Do not "
        "include tests or a step-by-step reasoning trace.\n\n"
        "```python\n{input}\n```"
    ),
    "unit_test_generation": (
        "Write pytest tests for the following Python function. Return only a single "
        "```python fenced block containing the test file.\n\n"
        "Rules:\n"
        "- Assume the function under test is already defined in the same module; do "
        "not import it.\n"
        "- Import only `pytest` and Python standard-library modules if needed.\n"
        "- Cover normal cases, boundary cases and error cases.\n"
        "- Do not modify or redefine the function under test.\n"
        "- Do not use network access, external services or filesystem fixtures.\n"
        "- Return code only, with no explanation.\n\n"
        "```python\n{input}\n```"
    ),
    "code_completion": (
        "Complete the next line of the following Python code. The supplied code "
        "ends immediately before the line to predict. Return only the missing "
        "line or lines, with no explanation and no code fences. Preserve the "
        "indentation and style, and do not repeat the supplied prefix.\n\n"
        "```python\n{input}\n```"
    ),
}

OUTPUT_CONTRACTS: dict[str, dict[str, Any]] = {
    "code_generation": {
        "format": "one fenced python code block containing the complete function",
        "must_include": ["a complete function definition with the requested name"],
        "must_not_include": ["explanations", "test code", "extra examples"],
    },
    "code_explanation": {
        "format": "four Markdown sections: Purpose, Parameters, Return value, Complexity",
        "must_include": ["## Purpose", "## Parameters", "## Return value", "## Complexity"],
        "must_not_include": ["chain-of-thought", "invented behaviour"],
    },
    "bug_detection": {
        "format": "one JSON object",
        "required_keys": ["has_bug", "location", "description", "fix"],
        "has_bug_type": "boolean",
        "must_not_include": ["Markdown fences", "prose outside the JSON"],
    },
    "code_refactoring": {
        "format": "one fenced python code block followed by a '### Changes' bullet list",
        "must_include": ["refactored function", "### Changes"],
        "must_not_include": ["tests", "new dependencies", "changed function name"],
    },
    "unit_test_generation": {
        "format": "one fenced python code block containing pytest tests",
        "must_include": ["pytest-style test functions"],
        "must_not_include": ["redefinition of the function under test", "network calls"],
    },
    "code_completion": {
        "format": "raw missing line(s), no fences, no explanation",
        "must_include": ["the continuation of the unfinished line or the next line"],
        "must_not_include": ["the supplied prefix", "Markdown fences"],
    },
}

VALIDATION_RULES: dict[str, list[str]] = {
    "code_generation": [
        "Extract the first python fenced block.",
        "Compile the extracted function.",
        "Run the hidden official tests in an isolated subprocess with a timeout.",
        "pass@1 is 1 only when every official test passes; report SyntaxError, RuntimeError and TestFailure separately.",
    ],
    "code_explanation": [
        "Check that the four required headings are present.",
        "Compute ROUGE-L against the reference docstring as a proxy only.",
        "Score Purpose, Parameters, Return value and Complexity with a 0-2 rubric; use human review on a sample.",
        "Do not claim that ROUGE-L measures semantic correctness.",
    ],
    "bug_detection": [
        "Parse the JSON object and require a boolean has_bug.",
        "Compare has_bug with the hidden binary label.",
        "Report precision, recall and F1; location/fix are qualitative unless a localisation reference exists.",
    ],
    "code_refactoring": [
        "Extract the first python fenced block.",
        "Compile the refactored function.",
        "Run the hidden reference tests; behaviour preservation requires all tests to pass.",
        "Flag a no-op when the normalized output is identical to the input.",
        "Report the change status separately from behaviour preservation.",
    ],
    "unit_test_generation": [
        "Extract the first python fenced block.",
        "Run the generated tests with pytest against the canonical solution; the suite is valid only if all tests pass.",
        "Run the same tests against the stored killed mutants and compute the mutation score.",
        "Report validity and mutation score separately; do not claim full semantic coverage.",
    ],
    "code_completion": [
        "Take the first non-empty output line as the prediction.",
        "Compare with the hidden target line using whitespace-insensitive exact match.",
        "Also report edit similarity (difflib ratio) as a partial-credit metric.",
        "Do not execute the completed snippet as the primary metric.",
    ],
}


def render_user(record: dict[str, Any]) -> str:
    task = record["task"]
    if task not in USER_TEMPLATES:
        raise KeyError(f"Unknown task: {task}")
    return USER_TEMPLATES[task].format(input=record["input"])


def build_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    """Return the provider-independent chat messages for one record."""
    task = record["task"]
    if task not in SYSTEM_PROMPTS:
        raise KeyError(f"Unknown task: {task}")
    return [
        {"role": "system", "content": SYSTEM_PROMPTS[task]},
        {"role": "user", "content": render_user(record)},
    ]


def prompt_fingerprint(record: dict[str, Any]) -> str:
    """Stable hash of the textual prompt, independent of the tokenizer."""
    payload = json.dumps(build_messages(record), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_chat_template(
    tokenizer: Any,
    record: dict[str, Any],
    add_generation_prompt: bool = True,
) -> str:
    """Apply the tokenizer's native chat template without changing content.

    The model adapter is intentionally thin: the messages are identical for
    every model, and only the tokenizer's own template is applied.
    """
    messages = build_messages(record)
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )
    # Deterministic fallback for a tokenizer without a chat template. This is
    # never used by the three selected Instruct models, but keeps the registry
    # testable offline.
    system = messages[0]["content"]
    user = messages[1]["content"]
    return f"### System\n{system}\n\n### User\n{user}\n\n### Assistant\n"


def load_record(task: str, split: str, index: int) -> dict[str, Any]:
    path = BENCHMARK_DIR / "datasets" / split / f"{task}.jsonl"
    with open(path, "r", encoding="utf-8") as handle:
        for current, line in enumerate(handle):
            if current == index:
                return json.loads(line)
    raise IndexError(f"{path} has no record at index {index}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=sorted(SYSTEM_PROMPTS))
    parser.add_argument("--split", default="test", choices=["development", "test"])
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--raw", action="store_true", help="Print the user prompt only")
    args = parser.parse_args()

    record = load_record(args.task, args.split, args.index)
    if args.raw:
        print(render_user(record))
    else:
        print(json.dumps(build_messages(record), ensure_ascii=False, indent=2))
    print(f"\n[prompt_fingerprint] {prompt_fingerprint(record)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
