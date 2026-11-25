import json, os

OUT = r"C:\LF\slm-se-assistant\research\01_benchmark\kaggle_runs\phi4_sft_smoke\phi4-sft-smoke.ipynb"

def md(s): return {"cell_type":"markdown","metadata":{},"source":s.splitlines(keepends=True)}
def code(s): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":s.splitlines(keepends=True)}

cells = []

cells.append(md("# Phi-4 SFT Smoke Test (Kaggle, T4)\n\nMission: validate the fine-tuning pipeline end-to-end on a tiny subset before the full run. QLoRA via Unsloth, single T4."))

cells.append(code("""# ---- Environment ----
import sys, subprocess
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])
try:
    import unsloth
    print("unsloth already installed:", unsloth.__version__ if hasattr(unsloth,'__version__') else 'ok')
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
DATASET_SLUG = "phi4-sft-pilot-formatted"
TRAIN_FILE = None
VAL_FILE = None
import glob
for p in glob.glob("/kaggle/input/**/*.jsonl", recursive=True):
    if "formatted" in p and "train" in p:
        TRAIN_FILE = p
    if "formatted" in p and "validation" in p:
        VAL_FILE = p
print("TRAIN_FILE", TRAIN_FILE)
print("VAL_FILE", VAL_FILE)
assert TRAIN_FILE and VAL_FILE, "formatted dataset not found under /kaggle/input"
MODE = "smoke"
MAX_STEPS = 20
EVAL_STEPS = 10
SAVE_STEPS = 20
PER_DEVICE_BS = 1
GRAD_ACCUM = 4
LR = 2e-4
MAX_SEQ_LEN = 2048
LORA_R = 16
LORA_ALPHA = 32
SEED = 42
import os
RESULTS_ROOT = "/kaggle/working/results"
RUN_ID = "phi4_sft_smoke"
OUT_DIR = os.path.join(RESULTS_ROOT, "smoke", "phi4mini", RUN_ID)
os.makedirs(OUT_DIR, exist_ok=True)
print("OUT_DIR", OUT_DIR)
"""))

cells.append(code("""# ---- Load dataset ----
import json
def read_jsonl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]
train_rows = read_jsonl(TRAIN_FILE)
val_rows = read_jsonl(VAL_FILE)
# smoke: tiny subset
train_rows = train_rows[:64]
val_rows = val_rows[:8]
print("train", len(train_rows), "val", len(val_rows))
# Build text field: prompt already ends with <|assistant|>, append completion
def to_text(r):
    return r["prompt"] + r["completion"]
train_texts = [{"text": to_text(r)} for r in train_rows]
val_texts = [{"text": to_text(r)} for r in val_rows]
from datasets import Dataset
train_ds = Dataset.from_list(train_texts)
val_ds = Dataset.from_list(val_texts)
print(train_ds[0]["text"][:300])
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
    max_steps = MAX_STEPS,
    per_device_train_batch_size = PER_DEVICE_BS,
    gradient_accumulation_steps = GRAD_ACCUM,
    learning_rate = LR,
    logging_steps = 5,
    eval_steps = EVAL_STEPS,
    save_steps = SAVE_STEPS,
    eval_strategy = "steps",
    save_strategy = "steps",
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

cells.append(code("""# ---- Save adapter + merged ----
ADAPTER_DIR = os.path.join(OUT_DIR, "adapter")
MERGED_DIR = os.path.join(OUT_DIR, "merged")
model.save_pretrained(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)
# merged (16-bit) for inference testing
model.save_pretrained_merged(MERGED_DIR, tokenizer, save_method="merged_16bit")
print("saved", ADAPTER_DIR, MERGED_DIR)
"""))

cells.append(code("""# ---- Quick eval: val loss ----
metrics = trainer.evaluate()
print("val metrics:", metrics)
import json
with open(os.path.join(OUT_DIR, "eval_metrics.json"),"w") as f:
    json.dump(metrics, f, indent=2)
"""))

cells.append(code("""# ---- Export ZIP + SHA256 ----
import zipfile, hashlib, glob
zip_path = "/kaggle/working/phi4-sft-smoke.zip"
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
print("wrote", OUT)
print("cells:", len(cells))

# write kernel-metadata.json
km = {
  "id": "merouanefaik/phi4-sft-smoke-test",
  "title": "Phi4 SFT Smoke Test",
  "code_file": "phi4-sft-smoke.ipynb",
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