# Kaggle MCP Inspection - Mission 02.2

Date: 2026-11-14

## Tools used (read-only)

| Tool | Purpose | Result |
|---|---|---|
| `get_accelerator_quota` | Confirm no GPU/TPU consumption | GPU used `0s` / `108000s`; TPU used `0s` / `72000s`; refresh `2026-11-21T00:00:00Z` |
| `list_models` | Find the three models on Kaggle Models | Qwen2.5-Coder and a Phi-4-mini mirror found |
| `get_model_variation` | Confirm framework/instance and usage path | Qwen `Transformers` variations confirmed |
| `list_model_variation_version_files` | Confirm safetensors sizes | Qwen 1.5B 3.09 GB, Qwen 3B 6.17 GB, Phi mirror 7.67 GB |

No mutating Kaggle tool was called.

## Tools intentionally not used

| Tool | Why not |
|---|---|
| `create_notebook_session` | Creates a notebook session and can allocate GPU; Mission 02.2 forbids launching a session. |
| `save_notebook` | Saves and runs the notebook from top to bottom; Mission 02.2 forbids executing it. |
| `create_model` / `update_model` | Not needed; the baseline uses existing models. |
| `upload_dataset_file` | The signature has no dataset slug/version identifier and there is no `create_dataset` tool in this MCP catalog; it cannot create the private dataset safely. |
| `update_dataset_metadata` | Requires an existing dataset; none was created. |

## Kaggle Model references

- Qwen2.5-Coder model page:
  https://www.kaggle.com/models/qwen-lm/qwen2.5-coder
- Qwen2.5-Coder 1.5B Instruct:
  https://www.kaggle.com/models/qwen-lm/qwen2.5-coder/Transformers/1.5b-instruct
  - Mounted path: `/kaggle/input/qwen2.5-coder/transformers/1.5b-instruct/1`
  - `model.safetensors`: 3,087,467,144 bytes (3.09 GB)
- Qwen2.5-Coder 3B Instruct:
  https://www.kaggle.com/models/qwen-lm/qwen2.5-coder/Transformers/3b-instruct
  - Mounted path: `/kaggle/input/qwen2.5-coder/transformers/3b-instruct/1`
  - Safetensors: 4,957,560,304 + 1,214,366,696 = 6,171,927,000 bytes (6.17 GB)
- Phi-4-mini-instruct (official Hugging Face):
  https://huggingface.co/microsoft/Phi-4-mini-instruct
- Optional Phi-4-mini community Kaggle mirror:
  https://www.kaggle.com/models/kentarctic/phi-4-mini-instruct
  - Framework/instance: `Transformers` / `official-from-huggingface`
  - Nested model path:
    `/kaggle/input/phi-4-mini-instruct/transformers/official-from-huggingface/1/phi-4-mini-instruct`
  - Safetensors: 4,903,637,712 + 2,768,428,504 = 7,672,066,216 bytes (7.67 GB)
  - Status: **unofficial mirror**. Prefer the Hugging Face model ID unless the
    mirror has been verified.

## Why no Kaggle resource was created

The MCP catalog exposes notebook-session, model, competition and dataset
metadata operations, but not a safe way to:

1. create a new private dataset from a local folder;
2. upload a set of files under a new dataset version;
3. write a notebook without running it.

Calling `save_notebook` or `create_notebook_session` would violate the
"do not launch the benchmark / do not consume GPU" rule. Therefore the
prepared Kaggle resource is the local private upload bundle:

```text
C:\LF\DLP\kaggle_upload\slm-benchmark-baseline\
```

The exact manual upload and notebook-creation steps are in
`benchmark/docs/KAGGLE_SETUP.md`.

## Quota confirmation

At inspection time:

```text
GPU: 0s used / 108000s allowed
TPU: 0s used /  72000s allowed
```

This is quota metadata only. No GPU session was created or used.
