# Code Generation Prompt

## 1. Objective

Generate a correct, executable Python implementation from a function signature
and natural-language/docstring specification. The reference tests are never
shown to the model.

## 2. System prompt

```text
You are a senior Python software engineer. Solve the programming task by producing a complete, executable Python implementation. Do not include explanations, tests, examples or step-by-step reasoning.
```

## 3. User prompt template

~~~text
Implement the following Python function. Return the complete function (signature included) in a single ```python fenced block. Do not include tests or explanations.

```python
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The function signature plus its docstring or natural-language specification. It contains no reference tests and no canonical solution. |

The prompt is rendered by `benchmark/prompts/prompt_registry.py::render_user`.
No model-specific string is added. The tokenizer's native chat template is
applied afterwards by `apply_chat_template`.

## 5. Expected response format

- Exactly one fenced `python` code block.
- The block contains the complete function definition, including the requested
  function name and signature.
- No tests, no examples, no prose after the block.

## 6. Validation rules

1. Extract the first fenced Python block.
2. Check that it compiles.
3. Run the hidden official tests in an isolated subprocess with a timeout and
   restricted builtins.
4. `pass@1 = 1` only if every official test passes.
5. Classify failures as `SyntaxError`, `RuntimeError`, `TestFailure` or
   `InfraError`. Do not count an infrastructure failure as a model failure.

## 7. Evaluation

- Primary metric: `pass@1` on HumanEval+ (164 tasks) and the reserved MBPP+
  slice.
- Secondary metrics: compilation rate and strict-compilation rate.
- The reference tests are in `benchmark/datasets/private/`, never in the
  model-facing JSONL.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same task order and the same hidden tests are used.
- The generation budget is fixed in the baseline configuration and must be
  identical for all models.
- No few-shot example is included, so no model family receives an advantage.
