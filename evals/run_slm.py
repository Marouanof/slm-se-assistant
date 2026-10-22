"""Bench SLM — 6 capabilities CDC sur les 20 taches fixes.

generation : prompt.md -> code (pytest caches + Ruff/Bandit).
completion : solution.py tronquee 50% -> fichier complet (memes tests).
bug_detection : solution.py -> OUI/NON (attendu OUI si owasp-like).
explanation : solution.py -> explication FR (proxy : nom fct + >=30 mots).
refactoring : solution.py -> code equivalent (tests caches + Ruff<=ref).
test_generation : prompt.md + solution.py -> tests pytest (run vs ref).

Usage :
  python evals/run_slm.py --capability code_generation --limit 20 --k 1
  python evals/run_slm.py --capability all --models m1,m2 --limit 20
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

EVALS_ROOT = Path(__file__).resolve().parent
TASKS_ROOT = EVALS_ROOT / "tasks"
PROJECT_ROOT = EVALS_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents import tools  # noqa: E402

SLM_HOST = tools.SLM_HOST
CODE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\s*(.*?)```", re.DOTALL)

CAPABILITIES = (
    "code_generation",
    "code_completion",
    "bug_detection",
    "code_explanation",
    "code_refactoring",
    "test_generation",
)


def extract_code(raw: str) -> str:
    m = CODE_RE.search(raw or "")
    if m:
        return m.group(1).strip()
    text = (raw or "").strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def ollama_generate(
    model: str,
    prompt: str,
    timeout_s: int = 120,
    temperature: float = 0.0,
    num_predict: int = 512,
) -> dict:
    started = time.perf_counter()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "seed": 42,
            "num_ctx": 4096,
        },
    }
    url = SLM_HOST + "/api/generate"
    resp = httpx.post(url, json=payload, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    latency_ms = int((time.perf_counter() - started) * 1000)
    eval_count = int(data.get("eval_count") or 0)
    eval_dur = int(data.get("eval_duration") or 0)
    prompt_dur = int(data.get("prompt_eval_duration") or 0)
    tps = round(eval_count / eval_dur * 1e9, 1) if eval_dur > 0 else 0.0
    return {
        "response": str(data.get("response", "")),
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "tokens_out": eval_count,
        "tokens_per_sec": tps,
        "ttft_ms": int(prompt_dur // 1_000_000),
        "latency_ms": latency_ms,
    }


def run_hidden_tests(task_dir: Path, code: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "solution.py").write_text(code, encoding="utf-8")
        try:
            src = task_dir / "test_hidden.py"
            shutil.copy(src, tmp / "test_hidden.py")
        except OSError as exc:
            return False, f"COPY_ERROR {exc}"
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_hidden.py", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
                cwd=str(tmp),
            )
            ok = proc.returncode == 0
            return ok, (proc.stdout + proc.stderr)[-1000:]
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT 30s"
        except Exception as exc:
            return False, f"ERROR {exc}"


def run_generated_tests(task_dir: Path, test_code: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ref = (task_dir / "solution.py").read_text(encoding="utf-8")
        (tmp / "solution.py").write_text(ref, encoding="utf-8")
        (tmp / "test_gen.py").write_text(test_code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_gen.py", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
                cwd=str(tmp),
            )
            ok = proc.returncode == 0
            return ok, (proc.stdout + proc.stderr)[-1000:]
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT 30s"
        except Exception as exc:
            return False, f"ERROR {exc}"


def static_counts(code: str) -> tuple[int, int]:
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "snippet.py"
        target.write_text(code, encoding="utf-8")
        ruff_n = len(tools._run_ruff(target))
        bandit_n = len(tools._run_bandit(target))
        return ruff_n, bandit_n


def build_prompt(capability: str, task_dir: Path, prompt_md: str) -> str:
    ref = (task_dir / "solution.py").read_text(encoding="utf-8")
    if capability == "code_generation":
        head = "Tu es un assistant code Python. "
        head += "Reponds UNIQUEMENT avec un bloc python."
        return head + "\n\n" + prompt_md + "\n"
    if capability == "code_completion":
        lines = ref.splitlines()
        cut = max(2, len(lines) // 2)
        prefix = "\n".join(lines[:cut])
        head = "Complete ce fichier Python. "
        head += "Reponds UNIQUEMENT avec le fichier complet en bloc."
        return head + "\n\n" + prefix + "\n# ... complete ...\n"
    if capability == "bug_detection":
        head = "Ce code contient-il un bug ou une vulnerabilite ? "
        head += "Reponds par OUI ou NON en premier mot, puis 1 ligne."
        return head + "\n\n```python\n" + ref + "\n```\n"
    if capability == "code_explanation":
        head = "Explique en francais, en 5 lignes max, "
        head += "ce que fait ce code et ses cas limites."
        return head + "\n\n```python\n" + ref + "\n```\n"
    if capability == "code_refactoring":
        head = "Refactorise ce code a comportement identique "
        head += "(plus lisible, sans faille). "
        head += "Reponds UNIQUEMENT avec le code complet en bloc."
        return head + "\n\n```python\n" + ref + "\n```\n"
    if capability == "test_generation":
        head = "Ecris des tests pytest pour ce code (10 tests max). "
        head += "Le code est dans solution.py : "
        head += "commence par 'from solution import ...'. "
        head += "Reponds UNIQUEMENT avec le fichier de test en bloc."
        body = "\n\nConsigne:\n" + prompt_md + "\nCode:\n```python\n"
        return head + body + ref + "\n```\n"
    raise ValueError(f"capability inconnue: {capability}")


def score_output(
    capability: str, task_dir: Path, response: str, meta: dict
) -> dict:
    if capability in ("code_generation", "code_completion"):
        code = extract_code(response)
        passed, out = run_hidden_tests(task_dir, code)
        ruff_n, bandit_n = static_counts(code)
        return {
            "pass": passed,
            "ruff_count": ruff_n,
            "bandit_count": bandit_n,
            "output_tail": out[-300:],
        }
    if capability == "bug_detection":
        expected = meta.get("category", "") == "owasp-like"
        first = (response or "").strip().upper()
        if first.startswith("OUI"):
            pred: bool | None = True
        elif first.startswith("NON"):
            pred = False
        else:
            pred = None
        ok = pred is not None and pred == expected
        return {
            "pass": bool(ok),
            "expected_bug": expected,
            "predicted_bug": pred,
            "output_tail": (response or "")[:300],
        }
    if capability == "code_explanation":
        text = response or ""
        ref = (task_dir / "solution.py").read_text(encoding="utf-8")
        syms = tools.search_symbols(ref)
        names = syms.get("functions", []) + syms.get("classes", [])
        hit = any(n and n.lower() in text.lower() for n in names)
        words = len(text.split())
        ok = bool(hit and words >= 30)
        return {
            "pass": ok,
            "mentions_symbol": bool(hit),
            "word_count": words,
            "output_tail": text[:300],
        }
    if capability == "code_refactoring":
        code = extract_code(response)
        passed, out = run_hidden_tests(task_dir, code)
        ruff_n, _ = static_counts(code)
        ref_ruff, _ = static_counts(
            (task_dir / "solution.py").read_text(encoding="utf-8")
        )
        ok = bool(passed and ruff_n <= ref_ruff)
        return {
            "pass": ok,
            "tests_pass": passed,
            "ruff_count": ruff_n,
            "ref_ruff_count": ref_ruff,
            "output_tail": out[-300:],
        }
    if capability == "test_generation":
        code = extract_code(response)
        clean = [ln for ln in code.splitlines() if not ln.strip().startswith("```")]
        code = "\n".join(clean).strip()
        n_assert = code.count("assert")
        passed, out = run_generated_tests(task_dir, code)
        ok = bool(passed and n_assert >= 2)
        return {
            "pass": ok,
            "tests_pass": passed,
            "assert_count": n_assert,
            "output_tail": out[-300:],
        }
    raise ValueError(f"capability inconnue: {capability}")


def bench_task(
    model: str,
    task_dir: Path,
    k: int,
    timeout_s: int,
    temperature: float,
    capability: str,
) -> list[dict]:
    prompt_md = (task_dir / "prompt.md").read_text(encoding="utf-8")
    meta = json.loads((task_dir / "meta.json").read_text(encoding="utf-8"))
    prompt = build_prompt(capability, task_dir, prompt_md)
    num_predict = 1024 if capability == "test_generation" else 512
    rows = []
    for i in range(k):
        try:
            gen = ollama_generate(
                model,
                prompt,
                timeout_s=timeout_s,
                temperature=temperature,
                num_predict=num_predict,
            )
            score = score_output(capability, task_dir, gen["response"], meta)
            row = {
                "model": model,
                "task_id": task_dir.name,
                "category": meta.get("category", ""),
                "capability": capability,
                "attempt": i + 1,
                "temperature": temperature,
                "prompt_tokens": gen["prompt_tokens"],
                "tokens_out": gen["tokens_out"],
                "tokens_per_sec": gen["tokens_per_sec"],
                "ttft_ms": gen["ttft_ms"],
                "latency_ms": gen["latency_ms"],
            }
            row.update(score)
            rows.append(row)
        except Exception as exc:
            rows.append({
                "model": model,
                "task_id": task_dir.name,
                "category": meta.get("category", ""),
                "capability": capability,
                "attempt": i + 1,
                "temperature": temperature,
                "pass": False,
                "error": str(exc)[:300],
            })
    return rows


def prf(y_true: list[bool], y_pred: list[bool]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / max(len(y_true), 1)
    return {"acc": acc, "prec": prec, "rec": rec, "f1": f1}


def summarize(all_rows: list[dict], caps: list[str], models: list[str]) -> None:
    for cap in caps:
        for model in models:
            rows = [r for r in all_rows if r["model"] == model]
            rows = [r for r in rows if r["capability"] == cap]
            n_task = len({r["task_id"] for r in rows})
            a1 = [r for r in rows if r.get("attempt") == 1]
            n1 = max(len(a1), 1)
            pass1 = sum(1 for r in a1 if r.get("pass")) / n1
            by_task: dict[str, bool] = {}
            for r in rows:
                tid = str(r["task_id"])
                done = by_task.get(tid, False) or bool(r.get("pass"))
                by_task[tid] = done
            n_tasks = max(len(by_task), 1)
            passk = sum(1 for v in by_task.values() if v) / n_tasks
            tps = [r.get("tokens_per_sec", 0) for r in rows]
            tps = [t for t in tps if isinstance(t, (int, float))]
            avg_tps = sum(tps) / max(len(tps), 1)
            msg = f"[{model}|{cap}] tasks={n_task} k=? "
            msg += f"pass@1={pass1:.0%} pass@k={passk:.0%} tps={avg_tps:.1f}"
            if cap == "bug_detection":
                yt = [bool(r.get("expected_bug")) for r in a1]
                yp = [bool(r.get("predicted_bug")) for r in a1]
                m = prf(yt, yp)
                n_raw = sum(1 for r in a1 if r.get("predicted_bug") is None)
                msg += f" acc={pass1:.0%} P={m['prec']:.0%}"
                msg += f" R={m['rec']:.0%} F1={m['f1']:.0%}"
                msg += f" raw={n_raw}"
            print(msg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=str, default="qwen2.5-coder:0.5b")
    ap.add_argument("--capability", type=str, default="code_generation")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", type=str, default="evals/results_slm.json")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.capability == "all":
        caps = list(CAPABILITIES)
    else:
        caps = [c.strip() for c in args.capability.split(",") if c.strip()]
        for c in caps:
            if c not in CAPABILITIES:
                raise SystemExit(f"capability inconnue: {c} (choix: {CAPABILITIES})")
    tasks = sorted([p for p in TASKS_ROOT.iterdir() if p.is_dir()])
    tasks = tasks[: args.limit]
    all_rows: list[dict] = []
    for cap in caps:
        for model in models:
            for task in tasks:
                tag = f"{model} {task.name} [{cap}] x{args.k}"
                print(tag + " ...", flush=True)
                all_rows.extend(bench_task(
                    model, task, args.k, args.timeout,
                    args.temperature, cap,
                ))

    out_arg = Path(args.out)
    if out_arg.is_absolute():
        out_path = out_arg
    else:
        out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summarize(all_rows, caps, models)
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
