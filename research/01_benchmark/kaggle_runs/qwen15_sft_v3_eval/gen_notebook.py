import json, os, re

OUT = r"C:\LF\slm-se-assistant\research\01_benchmark\kaggle_runs\qwen15_sft_v3_eval\qwen15-sft-v3-eval.ipynb"
SANDBOX = r"C:\LF\slm-se-assistant\research\01_benchmark\harness\scripts\sandbox_runner.py"

def md(s): return {"cell_type": "markdown", "metadata": {}, "source": s.splitlines(keepends=True)}
def code(s): return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": s.splitlines(keepends=True)}

base_nb = json.load(open(r"C:\LF\slm-se-assistant\research\01_benchmark\harness\notebooks\baseline_benchmark.ipynb", encoding="utf-8"))
base_cells = base_nb["cells"]

cells = []

cells.append(md("""# Qwen2.5-Coder-1.5B SFT v3 — evaluation + execution sandbox (Kaggle, T4)

Evaluates the **harness-aligned** SFT v3 adapter on all 6 tasks.

Unlike the previous evaluation notebook, the three tasks that can be checked
automatically are scored by **actually executing** the generated code against the
hidden reference tests in an isolated subprocess:

- code_generation: `pass@1` against HumanEval+ tests.
- code_refactoring: `pass@1` = observable behaviour preserved (MBPP+ tests).
- unit_test_generation: generated suite validity on the canonical solution +
  mutation kill rate over the stored mutants.

The sandbox uses per-process CPU/memory/process/file limits, a wall-clock
timeout and a static AST pre-check. Generated code is never run in the host
interpreter.
"""))

# ---- Cell 1: Environment ----
cells.append(code("""# Environment verification
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
    print("gpu", torch.cuda.get_device_name(0), "vram GB", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2))
"""))

# ---- Cell 2: Storage paths (patched for /kaggle/input/datasets/ mount) ----
storage_src = "".join(base_cells[5]["source"])
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
assert old_patterns in storage_src, "storage path patterns not found"
storage_src = storage_src.replace(old_patterns, new_patterns)
cells.append(code(storage_src))

# ---- Cell 3: Config (SFT v3 + sandbox backend) ----
cells.append(code("""# Benchmark configuration (Kaggle-only) - SFT v3 + sandbox execution
import json, os, random, glob, shutil, socket, uuid
from datetime import datetime, timezone

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
SHORT = "qwen-2.5-coder-1.5b-sft-v3"
MODEL_DIR = "qwen15_sft_v3"

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
MODEL_SOURCE = BASE_MODEL_SOURCE

# The training run is attached as a kernel source. Pick the checkpoint with the
# lowest validation loss from its train_history.json (fallback: final adapter).
_history_paths = glob.glob("/kaggle/input/**/train_history.json", recursive=True)
_best_step, _best_loss = None, None
if _history_paths:
    _history = json.load(open(_history_paths[0], encoding="utf-8"))
    _evals = [e for e in _history if "eval_loss" in e]
    if _evals:
        _best = min(_evals, key=lambda e: e["eval_loss"])
        _best_step = _best.get("step")
        _best_loss = _best["eval_loss"]

def _find_adapter():
    if _best_step is not None:
        hits = glob.glob(f"/kaggle/input/**/checkpoint-{_best_step}/adapter_config.json", recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    for pattern in ("/kaggle/input/**/adapter/adapter_config.json", "/kaggle/input/**/adapter_config.json"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    return None

ADAPTER_SOURCE = _find_adapter()
print("train history:", _history_paths[0] if _history_paths else None)
print("best eval_loss:", _best_loss, "at step:", _best_step)
print("ADAPTER_SOURCE (selected):", ADAPTER_SOURCE)
assert ADAPTER_SOURCE is not None, "No adapter found in /kaggle/input/. Attach qwen15-sft-v3 as a kernel source."

USE_ADAPTER = True
SINGLE_GPU = True
DEVICE_MAP = {"": 0} if SINGLE_GPU else "auto"
MAX_INPUT_TOKENS = 8192

# Execution is now performed by the embedded sandbox, never by the host.
EXECUTION_BACKEND = "sandbox_subprocess"
ALLOW_UNSANDBOXED_CODE_EXECUTION = False
TASKS_REQUIRING_EXECUTION = {
    "code_generation",
    "code_refactoring",
    "unit_test_generation",
}
assert EXECUTION_BACKEND in ("none", "sandbox_subprocess")
assert ALLOW_UNSANDBOXED_CODE_EXECUTION is False

print("Base model:", MODEL_ID, "| short:", SHORT, "| model_dir:", MODEL_DIR)
print("Base model source:", BASE_MODEL_SOURCE)
print("Adapter source:", ADAPTER_SOURCE)
print("MODE:", MODE, "| results subdir:", RESULTS_MODE_DIR)
print("Execution backend:", EXECUTION_BACKEND)

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
if _history_paths:
    shutil.copyfile(_history_paths[0], os.path.join(METADATA_DIR, "sft_v3_train_history.json"))
with open(os.path.join(METADATA_DIR, "sft_v3_adapter_choice.json"), "w", encoding="utf-8") as _f:
    json.dump({"adapter_source": ADAPTER_SOURCE, "best_step": _best_step, "best_eval_loss": _best_loss}, _f, indent=2)
"""))

# ---- Cell 4: Prompt registry ----
cells.append(code("".join(base_cells[9]["source"])))
# ---- Cell 5: Load datasets ----
cells.append(code("".join(base_cells[10]["source"])))

# ---- Cell 6: Model loading ----
cells.append(code("""# Load base model in FP16 + SFT v3 adapter via PEFT.
import time
import torch
import subprocess, sys
def pip(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", pkg])
try:
    import peft
    print("peft", peft.__version__)
except Exception as e:
    print("installing peft:", e)
    pip("peft")

# Kaggle's image ships torchao 0.10.0, but peft 0.21 requires >= 0.16 and
# raises ImportError instead of disabling the integration. The benchmark does
# not use torchao, so remove it before injecting the LoRA adapter.
subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "torchao"])

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
_total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
assert _total_vram_gb >= 15.0, f"Expected >=15 GB GPU; found {_total_vram_gb:.2f} GB."

# Qwen2.5 supports SDPA; eager is a Phi-4-only requirement and is much slower
# on T4. Use the model's optimized attention path.
meta = {"trust_remote_code": False, "attn": "sdpa"}
load_kwargs = {
    "torch_dtype": torch.float16,
    "device_map": DEVICE_MAP,
    "trust_remote_code": meta["trust_remote_code"],
    "low_cpu_mem_usage": True,
}
if meta["attn"] is not None:
    load_kwargs["attn_implementation"] = meta["attn"]

print("Loading tokenizer from adapter:", ADAPTER_SOURCE)
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_SOURCE, trust_remote_code=meta["trust_remote_code"])
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "left"

print("Loading base model from", BASE_MODEL_SOURCE)
t0 = time.time()
from transformers import AutoModelForCausalLM
base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_SOURCE, **load_kwargs)
print(f"Base model loaded in {time.time() - t0:.1f}s")

print("Applying PEFT adapter from", ADAPTER_SOURCE)
t0 = time.time()
from peft import PeftModel
model = PeftModel.from_pretrained(base_model, ADAPTER_SOURCE, torch_dtype=torch.float16)
model.eval()
model.config.use_cache = True
_eos_ids = [tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.eos_token_id]
_eos_ids = [i for i in _eos_ids if isinstance(i, int) and i >= 0]
model.generation_config.eos_token_id = list(dict.fromkeys(_eos_ids))
model.generation_config.pad_token_id = tokenizer.pad_token_id
print(f"Adapter applied in {time.time() - t0:.1f}s")
print("Model dtype:", next(model.parameters()).dtype)
print("Model device:", next(model.parameters()).device)
print("use_cache:", model.config.use_cache)
print("generation eos:", model.generation_config.eos_token_id)
print("generation pad:", model.generation_config.pad_token_id)
if torch.cuda.is_available():
    print("Allocated VRAM after load (GB):", round(torch.cuda.memory_allocated() / 1e9, 3))
    torch.cuda.reset_peak_memory_stats()
"""))

# ---- Cell 7: Generation helpers ----
gen_src = "".join(base_cells[14]["source"])
# Qwen2.5 instruct ends a turn with <|im_end|> (151645) or <|endoftext|>
# (151643). A fine-tuned adapter can ignore the base generation config and
# run to max_new_tokens, so make the stop tokens explicit.
_old_gen = "    gen_kwargs = dict("
_new_gen = (
    '    eos_ids = [tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.eos_token_id]\n'
    "    eos_ids = [i for i in eos_ids if isinstance(i, int) and i >= 0]\n"
    "    eos_ids = list(dict.fromkeys(eos_ids))\n"
    "    gen_kwargs = dict("
)
assert _old_gen in gen_src, "gen_kwargs block not found"
gen_src = gen_src.replace(_old_gen, _new_gen, 1)
_old_pad = (
    "        pad_token_id=tokenizer.pad_token_id,\n"
    "        streamer=streamer,"
)
_new_pad = (
    "        pad_token_id=tokenizer.pad_token_id,\n"
    "        eos_token_id=eos_ids,\n"
    "        streamer=streamer,"
)
assert _old_pad in gen_src, "pad/streamer block not found"
gen_src = gen_src.replace(_old_pad, _new_pad, 1)
assert "eos_token_id=eos_ids" in gen_src, "eos patch failed"
cells.append(code(gen_src))

# ---- Cell 8: Eval helpers (sandbox-backed for the three executable tasks) ----
eval_src = "".join(base_cells[16]["source"])
# Drop the hard "no execution" assertion and the host-side run_python guard.
eval_src = eval_src.replace(
    '''assert EXECUTION_BACKEND == "none", (
    "This notebook only supports EXECUTION_BACKEND='none'. "
    "Do not enable unsandboxed execution."
)

''', ""
)
eval_src = eval_src.replace(
    '''def run_python(program, timeout=10):
    # Hard block: no isolated execution backend is available.
    raise RuntimeError(
        "Refusing to execute generated code: no isolated sandbox backend is "
        "configured. This notebook performs static checks only. Do not replace "
        "this guard with an unsandboxed subprocess."
    )

''', ""
)

# Replace the three static eval functions with sandbox-backed versions.
eval_src = eval_src.replace(
    '''def eval_code_generation(record, output):
    code = extract_code_block(output)
    result = _execution_skipped()
    result["compile_ok"] = _static_syntax_ok(code)  # static syntax only
    result["static_only"] = True
    return result''',
    '''def eval_code_generation(record, output):
    code = extract_code_block(output)
    priv = load_private(record["id"], "code_generation")
    res = run_code_generation(code, priv["reference_tests"], timeout=10)
    return {
        "pass@1": res["pass@1"],
        "compile_ok": _static_syntax_ok(code),
        "executed": res["executed"],
        "timed_out": res["timed_out"],
        "returncode": res["returncode"],
        "reason": res["reason"],
        "stderr_tail": res["stderr_tail"][-500:],
        "execution_backend": EXECUTION_BACKEND,
    }''',
)
eval_src = eval_src.replace(
    '''def eval_code_refactoring(record, output):
    code = extract_code_block(output)
    result = _execution_skipped()
    result["compile_ok"] = _static_syntax_ok(code)  # static syntax only
    result["static_only"] = True
    result["changed"] = (re.sub(r"\\s+", "", code) != re.sub(r"\\s+", "", record["input"]))
    return result''',
    '''def eval_code_refactoring(record, output):
    code = extract_code_block(output)
    priv = load_private(record["id"], "code_refactoring")
    res = run_code_refactoring(code, priv["reference_tests"], timeout=10)
    return {
        "pass@1": res["pass@1"],
        "compile_ok": _static_syntax_ok(code),
        "changed": (re.sub(r"\\s+", "", code) != re.sub(r"\\s+", "", record["input"])),
        "executed": res["executed"],
        "timed_out": res["timed_out"],
        "returncode": res["returncode"],
        "reason": res["reason"],
        "stderr_tail": res["stderr_tail"][-500:],
        "execution_backend": EXECUTION_BACKEND,
    }''',
)
eval_src = eval_src.replace(
    '''def eval_unit_test_generation(record, output):
    tests = extract_code_block(output)
    result = _execution_skipped()
    result["syntax_ok"] = _static_syntax_ok(tests)
    result["n_tests"] = len(re.findall(r"def\\s+test_\\w+", tests))
    result["static_only"] = True
    return result''',
    '''def eval_unit_test_generation(record, output):
    tests = extract_code_block(output)
    priv = load_private(record["id"], "unit_test_generation")
    art = priv.get("private_artifacts") or {}
    canonical = art.get("canonical_solution") or record["input"]
    mutants = art.get("mutants") or []
    res = run_unit_tests(tests, canonical, priv["reference_tests"], mutants=mutants, timeout=10)
    return {
        "syntax_ok": _static_syntax_ok(tests),
        "n_tests": len(re.findall(r"def\\s+test_\\w+", tests)),
        "valid_suite": res["tests_pass_on_canonical"],
        "mutation_kill_rate": res["mutation_kill_rate"],
        "n_mutants": res["n_mutants"],
        "mutants_killed": res["mutants_killed"],
        "reason": res["reason"],
        "execution_backend": EXECUTION_BACKEND,
    }''',
)
assert "run_code_generation" in eval_src, "eval_code_generation patch failed"
assert "run_code_refactoring" in eval_src, "eval_code_refactoring patch failed"
assert "valid_suite" in eval_src, "eval_unit_test_generation patch failed"
cells.append(code(eval_src))

# ---- Cell 9: Sandbox runner (embedded so the notebook is self-contained) ----
sandbox_src = open(SANDBOX, encoding="utf-8").read()
# Drop the module self-test block; keep every function.
sandbox_src = re.sub(r'\nif __name__ == "__main__":.*\Z', "\n", sandbox_src, flags=re.DOTALL)
cells.append(code("# ---- Isolated execution sandbox (embedded) ----\n" + sandbox_src))

# ---- Cell 10: Checkpointing ----
checkpoint_src = "".join(base_cells[18]["source"])
checkpoint_src = checkpoint_src.replace(
    '        "note": "Kaggle-only temporary filesystem. No generated code is executed. Download the ZIP before disconnecting.",',
    '        "note": "Kaggle-only temporary filesystem. Generated code is scored in an isolated subprocess sandbox. Download the ZIP before disconnecting.",',
)
assert "isolated subprocess sandbox" in checkpoint_src, "run_metadata note patch failed"
cells.append(code(checkpoint_src))

# ---- Cell 11: Main loop (strip trailing marker) ----
main_loop_src = "".join(base_cells[20]["source"])
helper = '''import re as _re
def strip_end_turn(text):
    """Remove Qwen/Phi end-of-turn markers and the ### Changes section."""
    text = text.rstrip()
    if "### Changes" in text:
        text = text.split("### Changes")[0].rstrip()
    text = _re.sub(r"<\\|(?:im_end|im_start|endoftext)\\|>", "", text).rstrip()
    text = _re.sub(r'\\|[^\\n]*$', '', text).rstrip()
    return text

'''
main_loop_src = helper + main_loop_src
main_loop_src = main_loop_src.replace(
    'print("Tasks with skipped scoring:", sorted(TASKS_REQUIRING_EXECUTION))',
    'print("Tasks scored by the sandbox:", sorted(TASKS_REQUIRING_EXECUTION))',
)
main_loop_src = main_loop_src.replace(
    'print("No generated code was executed.")',
    'print("Generated code was scored inside the isolated sandbox.")',
)
main_loop_src = main_loop_src.replace(
    '            ev = EVAL_FUNCS[task](record, gen["output"])',
    '            ev = EVAL_FUNCS[task](record, strip_end_turn(gen["output"]))',
)
cells.append(code(main_loop_src))

# ---- Cell 12: Unload ----
cells.append(code("".join(base_cells[22]["source"])))

# ---- Cell 13: Export ----
cells.append(md("## 11. Export ZIP + SHA256 (Kaggle Output pane)\n\nCreates a ZIP containing the whole results/ tree, including execution metrics."))
cells.append(code("".join(base_nb["cells"][24]["source"])))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("wrote", OUT, "cells:", len(cells))

km = {
    "id": "merouanefaik/qwen15-sft-v3-eval",
    "title": "Qwen15 SFT v3 Eval",
    "code_file": "qwen15-sft-v3-eval.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,
    "dataset_sources": [
        "merouanefaik/slm-benchmark-baseline",
    ],
    "competition_sources": [],
    "kernel_sources": [
        "merouanefaik/qwen15-sft-v3",
    ],
}
with open(os.path.join(os.path.dirname(OUT), "kernel-metadata.json"), "w", encoding="utf-8") as f:
    json.dump(km, f, indent=2)
print("wrote kernel-metadata.json")
print("generator ready")
