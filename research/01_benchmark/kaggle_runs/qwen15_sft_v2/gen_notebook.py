import json, os

OUT = r"C:\LF\slm-se-assistant\research\01_benchmark\kaggle_runs\qwen15_sft_v2\qwen15-sft-v2.ipynb"

def md(s): return {"cell_type": "markdown", "metadata": {}, "source": s.splitlines(keepends=True)}
def code(s): return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s.splitlines(keepends=True)}

cells = []

cells.append(md("""# Qwen2.5-Coder-1.5B SFT v2 — harness-aligned data (Kaggle, T4)

Second fine-tuning attempt. The first run under-performed because the pilot data
used a different prompt format than the evaluation harness and every completion
ended with a stray `|` before the end-of-text token.

This run uses `slm-sft-v2`, which formats each row with the **exact**
`SYSTEM_PROMPTS` / `USER_TEMPLATES` from `prompt_registry.py`, renders the chat
with the tokenizer's own `apply_chat_template` (so training and inference are
byte-identical), and normalises completions (fenced code where the harness asks
for it, no stray `|`).

3 tasks with canonical answers: code_generation, unit_test_generation,
code_completion. Adapter-only export.
"""))

cells.append(code("""# ---- Environment ----
import sys, subprocess
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg])
try:
    import unsloth
    print("unsloth", getattr(unsloth, "__version__", "ok"))
except Exception as e:
    print("installing unsloth:", e)
    pip("unsloth")
    import unsloth
import trl, peft, accelerate, bitsandbytes, torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0), "vram GB", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2))
"""))

cells.append(code("""# ---- Config ----
import glob, os
MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
TRAIN_FILE = None
VAL_FILE = None
for p in glob.glob("/kaggle/input/**/*.jsonl", recursive=True):
    if "sft_v2_train" in os.path.basename(p):
        TRAIN_FILE = p
    if "sft_v2_validation" in os.path.basename(p):
        VAL_FILE = p
print("TRAIN_FILE", TRAIN_FILE)
print("VAL_FILE", VAL_FILE)
assert TRAIN_FILE and VAL_FILE, "slm-sft-v2 dataset not found"
NUM_EPOCHS = 2
PER_DEVICE_BS = 1
GRAD_ACCUM = 4
LR = 1e-4
MAX_SEQ_LEN = 2048
LORA_R = 16
LORA_ALPHA = 32
SEED = 42
RESULTS_ROOT = "/kaggle/working/results"
RUN_ID = "qwen15_sft_v2"
OUT_DIR = os.path.join(RESULTS_ROOT, "baseline", "qwen15_sft_v2", RUN_ID)
os.makedirs(OUT_DIR, exist_ok=True)
print("OUT_DIR", OUT_DIR)
"""))

cells.append(code("""# ---- Load model + tokenizer first (needed for apply_chat_template) ----
from unsloth import FastLanguageModel
import torch
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = MODEL_ID,
    max_seq_length = MAX_SEQ_LEN,
    dtype = None,
    load_in_4bit = True,
)
print("chat_template present:", bool(getattr(tokenizer, "chat_template", None)))
print("eos_token:", tokenizer.eos_token, "| eos_token_id:", tokenizer.eos_token_id)
"""))

cells.append(code("""# ---- Build training texts with the tokenizer's own chat template ----
import json
def read_jsonl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]
train_rows = read_jsonl(TRAIN_FILE)
val_rows = read_jsonl(VAL_FILE)
print("train", len(train_rows), "val", len(val_rows))

def to_text(r):
    messages = [
        {"role": "system", "content": r["system"]},
        {"role": "user", "content": r["user"]},
        {"role": "assistant", "content": r["completion"]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False)

train_texts = [{"text": to_text(r)} for r in train_rows]
val_texts = [{"text": to_text(r)} for r in val_rows]
print("sample formatted train text (first 1200 chars):\\n" + train_texts[0]["text"][:1200])
print("\\n...tail:", repr(train_texts[0]["text"][-120:]))

from datasets import Dataset
train_ds = Dataset.from_list(train_texts)
val_ds = Dataset.from_list(val_texts)
"""))

cells.append(code("""# ---- Attach LoRA ----
model = FastLanguageModel.get_peft_model(
    model,
    r = LORA_R,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = LORA_ALPHA,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = SEED,
)
print("lora attached")
"""))

cells.append(code("""# ---- Train ----
from trl import SFTTrainer
from transformers import TrainingArguments
args = TrainingArguments(
    output_dir = OUT_DIR,
    num_train_epochs = NUM_EPOCHS,
    per_device_train_batch_size = PER_DEVICE_BS,
    gradient_accumulation_steps = GRAD_ACCUM,
    learning_rate = LR,
    logging_steps = 20,
    eval_strategy = "epoch",
    save_strategy = "epoch",
    save_total_limit = None,
    fp16 = not torch.cuda.is_bf16_supported(),
    bf16 = torch.cuda.is_bf16_supported(),
    optim = "adamw_8bit",
    seed = SEED,
    report_to = "none",
)
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = train_ds,
    eval_dataset = val_ds,
    dataset_text_field = "text",
    max_seq_length = MAX_SEQ_LEN,
    packing = False,
    args = args,
)
trainer.train()
print("training done")
"""))

cells.append(code("""# ---- Save final adapter ----
ADAPTER_DIR = os.path.join(OUT_DIR, "adapter")
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)
print("saved adapter", ADAPTER_DIR)
"""))

cells.append(code("""# ---- Final val loss + per-epoch history ----
metrics = trainer.evaluate()
print("val metrics:", metrics)
with open(os.path.join(OUT_DIR, "eval_metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)
with open(os.path.join(OUT_DIR, "train_history.json"), "w") as f:
    json.dump(trainer.state.log_history, f, indent=2)
print("history:", json.dumps(trainer.state.log_history, indent=2))
"""))

cells.append(code("""# ---- Export ZIP + SHA256 ----
import zipfile, hashlib, os
zip_path = "/kaggle/working/qwen15-sft-v2.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(OUT_DIR):
        for fn in files:
            fp = os.path.join(root, fn)
            arc = os.path.relpath(fp, OUT_DIR)
            z.write(fp, arc)
print("zip", zip_path)
h = hashlib.sha256()
with open(zip_path, "rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        h.update(chunk)
print("sha256", h.hexdigest())
with open(zip_path + ".sha256", "w") as f:
    f.write(h.hexdigest() + "  " + os.path.basename(zip_path) + "\\n")
print("done")
"""))

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(nb, f, indent=1)
print("wrote", OUT, "cells:", len(cells))

km = {
    "id": "merouanefaik/qwen15-sft-v2",
    "title": "Qwen15 SFT v2",
    "code_file": "qwen15-sft-v2.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,
    "dataset_sources": ["merouanefaik/slm-sft-v2"],
    "competition_sources": [],
    "kernel_sources": [],
}
with open(os.path.join(os.path.dirname(OUT), "kernel-metadata.json"), "w") as f:
    json.dump(km, f, indent=2)
print("wrote kernel-metadata.json")
print("generator ready")
