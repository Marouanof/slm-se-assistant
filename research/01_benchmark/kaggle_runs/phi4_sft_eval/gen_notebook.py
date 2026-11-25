import json, os

OUT = r"C:\LF\slm-se-assistant\research\01_benchmark\kaggle_runs\phi4_sft_eval\phi4-sft-eval.ipynb"

def md(s): return {"cell_type":"markdown","metadata":{},"source":s.splitlines(keepends=True)}
def code(s): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":s.splitlines(keepends=True)}

# Read baseline notebook to copy cells
base_nb = json.load(open(r"C:\LF\slm-se-assistant\research\01_benchmark\harness\notebooks\baseline_benchmark.ipynb", encoding="utf-8"))
base_cells = base_nb["cells"]

cells = []

# ---- Markdown header ----
cells.append(md("# Phi-4 SFT Evaluation Benchmark (Kaggle, T4)\n\n"
    "Evaluates the **fine-tuned** Phi-4 (SFT adapter) on all 6 SE tasks.\n"
    "Compares against the base Phi-4 baseline results already in `results/baseline/phi4mini/`.\n\n"
    "Loads base model in FP16 + PEFT adapter from an attached Kaggle dataset.\n"
    "Recommended adapter: **checkpoint-203** (epoch 1, best val loss 0.5710)."))

# ---- Cell 1: Environment ----
cells.append(code(base_cells[3]["source"] if False else """# Environment verification
import sys, subprocess
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg])
try:
    import peft
    print("peft", peft.__version__)
except Exception as e:
    print("installing peft:", e)
    pip("peft")
import torch, transformers, accelerate
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0), "vram GB", round(torch.cuda.get_device_properties(0).total_memory/1e9,2))
"""))

# ---- Cell 2: Storage paths (patched for new /kaggle/input/datasets/ mount) ----
storage_src = "".join(base_cells[5]["source"])
# Add new glob patterns for the /kaggle/input/datasets/ mount path
old_patterns = '''_candidates = []
for _pattern in (
    os.path.join(INPUT_ROOT, "*", "benchmark"),
    os.path.join(INPUT_ROOT, "*", "*", "benchmark"),
    os.path.join(INPUT_ROOT, "*", "*", "*", "benchmark"),
):'''
new_patterns = '''_candidates = []
for _pattern in (
    os.path.join(INPUT_ROOT, "*", "benchmark"),
    os.path.join(INPUT_ROOT, "*", "*", "benchmark"),
    os.path.join(INPUT_ROOT, "*", "*", "*", "benchmark"),
    os.path.join(INPUT_ROOT, "datasets", "*", "*", "benchmark"),
    os.path.join(INPUT_ROOT, "datasets", "*", "*", "*", "benchmark"),
    os.path.join(INPUT_ROOT, "datasets", "*", "*", "*", "*", "benchmark"),
):'''
storage_src = storage_src.replace(old_patterns, new_patterns)
cells.append(code(storage_src))

# ---- Cell 3: Config (modified) ----
cells.append(code("""# Benchmark configuration (Kaggle-only) - SFT variant
import os, random, glob, socket, uuid
from datetime import datetime, timezone

MODEL_CHOICES = [
    "microsoft/Phi-4-mini-instruct (base + SFT adapter)",
]

# Base model ID (for metadata consistency with baseline)
MODEL_ID = "microsoft/Phi-4-mini-instruct"

# SFT-specific identifiers (distinct from base run)
SHORT = "phi-4-mini-sft"
MODEL_DIR = "phi4mini_sft"

MODE = "full"
if MODE == "baseline":
    print("MODE='baseline' is a legacy alias; using MODE='full'.")
    MODE = "full"
SMOKE_PER_TASK = 3
assert MODE in ("smoke_test", "full"), MODE
MODE_DIR = {"full": "baseline", "smoke_test": "smoke_test"}
RESULTS_MODE_DIR = MODE_DIR[MODE]

GEN_CONFIG = {
    "temperature": 0.0,
    "do_sample": False,
    "top_p": 1.0,
    "max_new_tokens": 512,
    "repetition_penalty": 1.0,
}
SEED = 42
random.seed(SEED)

# Base model metadata (same as baseline for loading)
BASE_META = {
    "trust_remote_code": True,
    "attn": "eager",
}

# Optional read-only Kaggle Models inputs for the BASE model.
BASE_MODEL_SOURCES = {
    "microsoft/Phi-4-mini-instruct": [
        "/kaggle/input/phi-4-mini-instruct/transformers/official-from-huggingface/1",
        "/kaggle/input/phi-4-mini-instruct/transformers/official-from-huggingface/1/phi-4-mini-instruct",
    ],
}

def resolve_base_source(model_id):
    for candidate in BASE_MODEL_SOURCES.get(model_id, []):
        if os.path.isfile(os.path.join(candidate, "config.json")):
            return candidate
    return model_id

BASE_MODEL_SOURCE = resolve_base_source(MODEL_ID)
MODEL_SOURCE = BASE_MODEL_SOURCE  # alias for baseline main loop compatibility

# Auto-discover the SFT adapter in mounted Kaggle datasets.
ADAPTER_SOURCE = None
for p in glob.glob("/kaggle/input/**/adapter_config.json", recursive=True):
    ADAPTER_SOURCE = os.path.dirname(p)
    break
print("ADAPTER_SOURCE (auto-discovered):", ADAPTER_SOURCE)
assert ADAPTER_SOURCE is not None, "No adapter_config.json found in /kaggle/input/. Attach the SFT adapter dataset."

USE_ADAPTER = True

# Single GPU only.
SINGLE_GPU = True
DEVICE_MAP = {"": 0} if SINGLE_GPU else "auto"

MAX_INPUT_TOKENS = 8192

# Safety gate
EXECUTION_BACKEND = "none"
ALLOW_UNSANDBOXED_CODE_EXECUTION = False
TASKS_REQUIRING_EXECUTION = {
    "code_generation",
    "code_refactoring",
    "unit_test_generation",
}
assert EXECUTION_BACKEND == "none"
assert ALLOW_UNSANDBOXED_CODE_EXECUTION is False

print("Base model:", MODEL_ID, "| short:", SHORT, "| model_dir:", MODEL_DIR)
print("Base model source:", BASE_MODEL_SOURCE)
print("Adapter source:", ADAPTER_SOURCE)
print("MODE:", MODE, "| results subdir:", RESULTS_MODE_DIR)
print("Execution backend:", EXECUTION_BACKEND)

# Run ID
try:
    RUN_IDS
except NameError:
    RUN_IDS = {}
_run_key = (MODE, MODEL_DIR)
if _run_key not in RUN_IDS:
    _stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    RUN_IDS[_run_key] = f"{MODEL_DIR}_{MODE}_{_stamp}_{socket.gethostname()}_{uuid.uuid4().hex[:8]}"
    print("Generated RUN_ID =", RUN_IDS[_run_key])
else:
    print("Reusing RUN_ID =", RUN_IDS[_run_key])
RUN_ID = RUN_IDS[_run_key]
RUN_DIR = os.path.join(RESULTS_ROOT, RESULTS_MODE_DIR, MODEL_DIR, RUN_ID)
os.makedirs(RUN_DIR, exist_ok=True)
METADATA_DIR = os.path.join(RESULTS_ROOT, "metadata")
os.makedirs(METADATA_DIR, exist_ok=True)
assert RUN_DIR.startswith(RESULTS_ROOT + os.sep), RUN_DIR
print("RUN_ID =", RUN_ID)
print("RUN_DIR =", RUN_DIR)
"""))

# ---- Cell 4: Prompt registry (copy from baseline cell 9) ----
cells.append(code("".join(base_cells[9]["source"])))

# ---- Cell 5: Load datasets (copy from baseline cell 10) ----
cells.append(code("".join(base_cells[10]["source"])))

# ---- Cell 6: Model loading (Unsloth adapter, avoids peft/transformers mismatch) ----
cells.append(code("""# Load base model in FP16 + SFT adapter via Unsloth (avoids peft/transformers version mismatch).
import time
import torch
import subprocess, sys
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg])
try:
    import unsloth
    print("unsloth", getattr(unsloth, "__version__", "ok"))
except Exception as e:
    print("installing unsloth:", e)
    pip("unsloth")
    import unsloth
from unsloth import FastLanguageModel

if "model" in globals() or "tokenizer" in globals():
    raise RuntimeError("A model/tokenizer is already loaded. Run the unload cell first.")

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

assert torch.cuda.is_available(), "No GPU available. Set Accelerator -> GPU T4 x1."
_gpu_count = torch.cuda.device_count()
print("CUDA device count:", _gpu_count)
for _i in range(_gpu_count):
    _p = torch.cuda.get_device_properties(_i)
    print(f"  GPU {_i}: {_p.name} | {_p.total_memory / 1e9:.2f} GB")

if SINGLE_GPU:
    torch.cuda.set_device(0)
    if _gpu_count > 1:
        print("WARNING: multiple GPUs visible; device_map forces GPU 0 only.")

_gpu_name = torch.cuda.get_device_name(0)
_total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
print("Active GPU:", _gpu_name, "| VRAM (GB):", round(_total_vram_gb, 2))
assert _total_vram_gb >= 15.0, f"Expected >=15 GB GPU; found {_total_vram_gb:.2f} GB."

meta = {"trust_remote_code": False, "attn": "eager"}

load_kwargs = {
    "torch_dtype": torch.float16,
    "device_map": DEVICE_MAP,
    "trust_remote_code": meta["trust_remote_code"],
    "low_cpu_mem_usage": True,
}
if meta["attn"] is not None:
    load_kwargs["attn_implementation"] = meta["attn"]

# Load tokenizer from adapter dir (preserves chat template)
print("Loading tokenizer from adapter:", ADAPTER_SOURCE)
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_SOURCE, trust_remote_code=meta["trust_remote_code"])
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "left"

# Load base model
print("Loading base model from", BASE_MODEL_SOURCE)
t0 = time.time()
from transformers import AutoModelForCausalLM
base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_SOURCE, **load_kwargs)
print(f"Base model loaded in {time.time()-t0:.1f}s")

# Apply PEFT adapter
print("Applying PEFT adapter from", ADAPTER_SOURCE)
t0 = time.time()
from peft import PeftModel
model = PeftModel.from_pretrained(base_model, ADAPTER_SOURCE, torch_dtype=torch.float16)
model.eval()
model.config.use_cache = True
print(f"Adapter applied in {time.time()-t0:.1f}s")

print("Model dtype:", next(model.parameters()).dtype)
print("Model device:", next(model.parameters()).device)
if torch.cuda.is_available():
    print("Allocated VRAM after load (GB):", round(torch.cuda.memory_allocated() / 1e9, 3))
    torch.cuda.reset_peak_memory_stats()
"""))

# ---- Cell 7: Generation helpers (copy from baseline cell 14) ----
cells.append(code("".join(base_cells[14]["source"])))

# ---- Cell 8: Eval helpers (copy from baseline cell 16) ----
cells.append(code("".join(base_cells[16]["source"])))

# ---- Cell 9: Checkpointing (copy from baseline cell 18, but need to fix MODEL_ID refs -> use MODEL_ID var) ----
# The baseline checkpointing cell uses MODEL_ID in run_metadata; our MODEL_ID is base model id which is fine.
cells.append(code("".join(base_cells[18]["source"])))

# ---- Cell 10: Main loop (patched to strip end-of-turn marker before eval) ----
main_loop_src = "".join(base_cells[20]["source"])
# Add strip_end_turn helper before the main loop
helper = '''import re as _re
def strip_end_turn(text):
    """Remove trailing Phi-4 end-of-turn marker (| token) and ### Changes section."""
    text = text.rstrip()
    # Strip everything after ### Changes (refactoring explanation)
    if "### Changes" in text:
        text = text.split("### Changes")[0].rstrip()
    # Remove trailing |... end-of-turn marker
    text = _re.sub(r'\\|[^\\n]*$', '', text).rstrip()
    return text

'''
main_loop_src = helper + main_loop_src
# Patch the eval call to use stripped output
main_loop_src = main_loop_src.replace(
    '            ev = EVAL_FUNCS[task](record, gen["output"])',
    '            ev = EVAL_FUNCS[task](record, strip_end_turn(gen["output"]))'
)
cells.append(code(main_loop_src))

# ---- Cell 11: Unload (copy from baseline cell 22) ----
cells.append(code("".join(base_cells[22]["source"])))

# ---- Cell 12: Export ZIP (copy from baseline cell 24's code? Actually cell 24 is markdown. Let me check what cell 23 has) ----
# Cell 23 is markdown (section 11). The actual export code... let me check if there's a code cell after. Let me look at cells 23-25.
# From the dump, cell 23 is markdown. Let me check cell 24 and 25.
cells.append(md("## 11. Export ZIP + SHA256 (Kaggle Output pane)\n\nCreates ZIP containing the whole results/ tree."))

# Need to find the export code cell. Let me check remaining cells.
nb2 = json.load(open(r"C:\LF\slm-se-assistant\research\01_benchmark\harness\notebooks\baseline_benchmark.ipynb", encoding="utf-8"))
for i in range(23, len(nb2["cells"])):
    c = nb2["cells"][i]
    print(f"cell {i}: {c['cell_type']} | {str(c['source'][:2])[:60]}")
    if c["cell_type"] == "code":
        print("".join(c["source"])[:500])

# ---- Cell 12: Export ZIP (copy from baseline cell 24) ----
cells.append(code("".join(nb2["cells"][24]["source"])))

# Write notebook
os.makedirs(os.path.dirname(OUT), exist_ok=True)
nb = {"cells": cells, "metadata": {"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}}, "nbformat":4, "nbformat_minor":5}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("wrote", OUT, "cells:", len(cells))