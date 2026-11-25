# Code Explanation Prompt

## 1. Objective

Generate a structured explanation of a Python function from its source code.
The reference docstring is hidden from the model and is used only for
evaluation.

## 2. System prompt

```text
You are a senior software engineer. Explain Python code accurately and concisely for a developer who can already read Python. Do not invent behaviour that is not supported by the code. Do not include step-by-step reasoning.
```

## 3. User prompt template

~~~text
Explain the following Python function. Use exactly these four Markdown sections, in this order:
## Purpose
## Parameters
## Return value
## Complexity

If a section does not apply, write "Not applicable". State the time and space complexity in Big-O notation when it can be determined from the snippet; otherwise write "Not determinable from the snippet". Do not include the original code again.

```python
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The function source code with the reference docstring removed. |

## 5. Expected response format

- `## Purpose`: one or two sentences.
- `## Parameters`: one bullet per parameter, with name, type (if visible) and role.
- `## Return value`: what is returned and under what conditions.
- `## Complexity`: Big-O time and space when determinable.
- No chain-of-thought, no invented behaviour, no reproduction of the code.

## 6. Validation rules

1. Check that the four required headings are present.
2. Compute ROUGE-L against the hidden reference docstring as a proxy only.
3. Score each section with a 0-2 rubric during human review on a sample.
4. Do not claim that ROUGE-L measures semantic correctness.

## 7. Evaluation

- Primary metric: ROUGE-L F1 against the hidden reference docstring.
- Secondary metric: manual rubric (Purpose, Parameters, Return value, Complexity).
- The hidden reference docstrings are in `benchmark/datasets/private/`.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same code snippets and the same hidden references are used.
- No few-shot example is included.
