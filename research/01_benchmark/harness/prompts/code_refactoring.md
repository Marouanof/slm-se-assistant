# Code Refactoring Prompt

## 1. Objective

Refactor a Python function without changing its observable behaviour. Behaviour
preservation is checked with hidden reference tests; no single textual
reference refactor is fabricated.

## 2. System prompt

```text
You are a senior Python software engineer. Refactor the supplied function without changing its observable behaviour. Preserve the public signature, return semantics and error behaviour. Do not add new third-party dependencies.
```

## 3. User prompt template

~~~text
Refactor the following Python function. Preserve its public signature, return values and observable behaviour. Return exactly two parts:
1. A single ```python fenced block with the complete refactored function.
2. A `### Changes` section with 1 to 5 bullet points describing the main changes.

Do not change the function name and do not add new dependencies. Do not include tests or a step-by-step reasoning trace.

```python
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The original Python function, optionally preceded by a `#` task comment. |

## 5. Expected response format

- One fenced `python` block containing the complete refactored function.
- A `### Changes` section with 1 to 5 bullet points.
- No tests, no prose reasoning trace.

## 6. Validation rules

1. Extract the first Python fenced block.
2. Check that it compiles.
3. Run the hidden reference tests; behaviour preservation requires all tests to
   pass.
4. Flag a no-op when the normalized output is identical to the input.
5. Report change status separately from behaviour preservation.

## 7. Evaluation

- Primary metric: behaviour preservation (all hidden reference tests pass).
- Secondary metrics: no-op rate and AST-based change indicators.
- No human-written reference refactor is claimed; refactoring quality beyond
  behaviour preservation requires human review.
- Hidden tests are in `benchmark/datasets/private/`.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same functions and the same hidden tests are used.
- No few-shot example is included.
- The input is the full original function, not a diff or a hint.
