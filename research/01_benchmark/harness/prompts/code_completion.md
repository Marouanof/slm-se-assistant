# Code Completion Prompt

## 1. Objective

Predict the next line of Python code from a supplied prefix. The hidden target
line is used only for evaluation.

## 2. System prompt

```text
You are a Python autocomplete engine. Complete the next line of the supplied code. Preserve the existing style and context. Do not repeat the supplied prefix. Do not add explanations.
```

## 3. User prompt template

~~~text
Complete the next line of the following Python code. The supplied code ends immediately before the line to predict. Return only the missing line or lines, with no explanation and no code fences. Preserve the indentation and style, and do not repeat the supplied prefix.

```python
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The code prefix ending immediately before the target line. |

## 5. Expected response format

- Raw line or lines only.
- No Markdown fences and no explanation.
- The first non-empty output line is the prediction.

## 6. Validation rules

1. Take the first non-empty output line as the prediction.
2. Compare it with the hidden target line using whitespace-insensitive exact
   match.
3. Report edit similarity (difflib ratio) as a partial-credit metric.
4. Do not execute the completed snippet as the primary metric.

## 7. Evaluation

- Primary metric: whitespace-insensitive exact match.
- Secondary metric: edit similarity.
- The hidden targets are in `benchmark/datasets/private/`.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same prefixes and the same hidden targets are used.
- No few-shot example is included.
- The completion budget is fixed in the baseline configuration.
