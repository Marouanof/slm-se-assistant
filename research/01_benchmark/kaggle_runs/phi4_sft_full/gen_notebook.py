import json, os

OUT = r"C:\LF\slm-se-assistant\research\01_benchmark\kaggle_runs\phi4_sft_full\phi4-sft-full.ipynb"

def md(s): return {"cell_type":"markdown","metadata":{},"source":s.splitlines(keepends=True)}
def code(s): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":s.splitlines(keepends=True)}

cells = []

cells.append(md("# Phi-4 SFT Full Run (Kaggle, T4)\n\nFull fine-tuning on the pilot-formatted dataset (3 tasks: code_generation, unit_test_generation, code_completion). Adapter-only export (no merged 16-bit) to keep output small."))

cells.append(code("""# ---- Environment ----
import sys, subprocess
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg])
try:
    import unsloth
    print("unsloth", getattr(unsloth,'__version__','ok'))
except Exception as e:
    print("installing unsloth:", e)
    pip("unsloth")
    import unsloth
import trl, peft, accelerate, bitsandbytes, torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0), "vram GB", round(torch.cuda.get_device_properties(0).total_memory/1e9,2))
"""))

cells.append(code("""# ---- Config ----
MODEL_ID = "microsoft/Phi-4-mini-instruct"
TRAIN_FILE = None
VAL_FILE = None
import glob, os
for p in glob.glob("/kaggle/input/**/*.jsonl", recursive=True):
    if "formatted" in p and "train" in p:
        TRAIN_FILE = p
    if "formatted" in p and "validation" in p:
        VAL_FILE = p
print("TRAIN_FILE", TRAIN_FILE)
print("VAL_FILE", VAL_FILE)
assert TRAIN_FILE and VAL_FILE, "formatted dataset not found"
MODE = "full"
NUM_EPOCHS = 3
PER_DEVICE_BS = 1
GRAD_ACCUM = 4
LR = 2e-4
MAX_SEQ_LEN = 2048
LORA_R = 16
LORA_ALPHA = 32
SEED = 42
RESULTS_ROOT = "/kaggle/working/results"
RUN_ID = "phi4_sft_full"
OUT_DIR = os.path.join(RESULTS_ROOT, "baseline", "phi4mini", RUN_ID)
os.makedirs(OUT_DIR, exist_ok=True)
print("OUT_DIR", OUT_DIR)
"""))

cells.append(code("""# ---- Load dataset (full) ----
import json
def read_jsonl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]
train_rows = read_jsonl(TRAIN_FILE)
val_rows = read_jsonl(VAL_FILE)
print("train", len(train_rows), "val", len(val_rows))
def to_text(r):
    return r["prompt"] + r["completion"]
train_texts = [{"text": to_text(r)} for r in train_rows]
val_texts = [{"text": to_text(r)} for r in val_rows]
from datasets import Dataset
train_ds = Dataset.from_list(train_texts)
val_ds = Dataset.from_list(val_texts)
"""))

cells.append(code("""# ---- Load model (QLoRA 4-bit) ----
from unsloth import FastLanguageModel
import torch
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = MODEL_ID,
    max_seq_length = MAX_SEQ_LEN,
    dtype = None,
    load_in_4bit = True,
)
model = FastLanguageModel.get_peft_model(
    model,
    r = LORA_R,
    target_modules = ["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    lora_alpha = LORA_ALPHA,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = SEED,
)
print("model loaded")
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

cells.append(code("""# ---- Save adapter only (no merged, keep output small) ----
ADAPTER_DIR = os.path.join(OUT_DIR, "adapter")
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)
print("saved adapter", ADAPTER_DIR)
"""))

cells.append(code("""# ---- Eval val loss ----
metrics = trainer.evaluate()
print("val metrics:", metrics)
import json
with open(os.path.join(OUT_DIR, "eval_metrics.json"),"w") as f:
    json.dump(metrics, f, indent=2)
"""))

cells.append(code("""# ---- Export ZIP + SHA256 (adapter + metrics only) ----
import zipfile, hashlib, os
zip_path = "/kaggle/working/phi4-sft-full.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root,_,files in os.walk(OUT_DIR):
        for fn in files:
            fp = os.path.join(root, fn)
            arc = os.path.relpath(fp, OUT_DIR)
            z.write(fp, arc)
print("zip", zip_path)
h = hashlib.sha256()
with open(zip_path,"rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        h.update(chunk)
print("sha256", h.hexdigest())
with open(zip_path+".sha256","w") as f:
    f.write(h.hexdigest()+"  "+os.path.basename(zip_path)+"\\n")
print("done")
"""))

nb = {"cells": cells, "metadata": {"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}}, "nbformat":4, "nbformat_minor":5}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(nb, f, indent=1)
print("wrote", OUT, "cells:", len(cells))

km = {
  "id": "merouanefaik/phi4-sft-full",
  "title": "Phi4 SFT Full",
  "code_file": "phi4-sft-full.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": True,
  "enable_gpu": True,
  "enable_internet": True,
  "dataset_sources": ["merouanefaik/phi4-sft-pilot-formatted"],
  "competition_sources": [],
  "kernel_sources": []
}
with open(os.path.join(os.path.dirname(OUT), "kernel-metadata.json"), "w") as f:
    json.dump(km, f, indent=2)
print("wrote kernel-metadata.json")
print("generator ready")