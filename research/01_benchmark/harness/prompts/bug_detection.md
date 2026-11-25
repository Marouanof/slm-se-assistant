# Bug Detection Prompt

## 1. Objective

Decide whether a C function contains a defect and, when applicable, identify
its location and a short correction. The hidden binary label is used only for
evaluation.

## 2. System prompt

```text
You are a senior C code reviewer. Decide whether the provided C function contains a defect. Base your answer only on the code. Do not include hidden reasoning or speculative issues that are not visible in the code.
```

## 3. User prompt template

~~~text
Review the following C function for a defect. Return exactly one JSON object with these keys:
{"has_bug": true or false, "location": "line or function, or empty string", "description": "short explanation", "fix": "short correction or empty string"}

Rules:
- `has_bug` must be a JSON boolean.
- Set `location` and `fix` to an empty string when `has_bug` is false.
- Do not wrap the JSON in Markdown fences.
- Return JSON only, with no prose before or after it.

```c
{input}
```
~~~

## 4. Variables

| Variable | Required | Description |
|---|---|---|
| `input` | yes | The C function source code. |

## 5. Expected response format

- Exactly one JSON object with the keys `has_bug`, `location`, `description`
  and `fix`.
- `has_bug` is a JSON boolean.
- No Markdown fences and no text outside the JSON.

## 6. Validation rules

1. Parse the JSON object and require a boolean `has_bug`.
2. Compare `has_bug` with the hidden binary label.
3. Report precision, recall and F1.
4. `location` and `fix` are qualitative unless a localisation reference exists.

## 7. Evaluation

- Primary metric: binary precision, recall and F1 on `has_bug`.
- Secondary: qualitative review of `location` and `fix`.
- The hidden labels are in `benchmark/datasets/private/`.

## 8. Fairness notes

- The same system and user templates are used for all three models.
- The same C snippets and the same hidden labels are used.
- No few-shot example is included.
