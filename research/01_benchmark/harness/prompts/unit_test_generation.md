# Unit Test Generation Prompt

## 1. Objective

Generate executable pytest tests for a Python function. Tests are run against the
hidden canonical solution and against generated mutants.

## 2. System prompt

```text
You are a senior Python test engineer. Write executable pytest tests for the supplied function. Cover normal, boundary and error cases. Do not use network access, external services or filesystem fixtures. Do not modify the function under test.
```

## 3. User prompt template

~~~text
Write pytest tests for the following Python function. Return only a single ```python fenced block containing the test file.

Rules:
- Assume the function under test is already defined in the same module; do not import it.
- Import only `pytest` and Python standard-library modules if needed.
- Cover normal cases, boundary cases and error cases.
- Do not modify or redefine the function under test.
- Do not use network access, external services or filesystem fixtures.
- Return code only, with no explanation.

```python
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The Python function under test, optionally preceded by a `#` task comment. |

## 5. Expected response format

- One fenced `python` block containing the test file.
- Tests use pytest conventions.
- No redefinition of the function under test.
- No explanation outside the block.

## 6. Validation rules

1. Extract the first Python fenced block.
2. Run the generated tests with pytest against the canonical solution.
3. The suite is valid only if all tests pass.
4. Run the same tests against the stored killed mutants and compute the
   mutation score.
5. Report validity and mutation score separately.

## 7. Evaluation

- Primary metric: mutation score on stored killed mutants.
- Secondary metric: validity (all tests pass on the canonical solution).
- Coverage is documented as a future extension.
- Hidden mutants are in `benchmark/datasets/private/`.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same functions and the same hidden mutants are used.
- No few-shot example is included.
- Tests are not allowed to redefine the function under test.
