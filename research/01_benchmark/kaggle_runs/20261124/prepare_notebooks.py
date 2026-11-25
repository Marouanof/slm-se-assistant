import json
from pathlib import Path

ROOT = Path(r"C:\LF\DLP\benchmark\kaggle_runs\20261124")
SRC = Path(r"C:\LF\DLP\benchmark\harness\notebooks\baseline_benchmark.ipynb")

BASE = json.loads(SRC.read_text(encoding="utf-8"))


def make_notebook(model_id: str, mode: str) -> dict:
    nb = json.loads(json.dumps(BASE))
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = []
        for line in cell.get("source", []):
            line = line.replace(
                'MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"',
                f'MODEL_ID = "{model_id}"',
            )
            line = line.replace('MODE = "full"', f'MODE = "{mode}"')
            source.append(line)
        cell["source"] = source
    return nb


def write_notebook(path: Path, model_id: str, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nb = make_notebook(model_id, mode)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")


def write_metadata(path: Path, kernel_id: str, title: str, code_file: str) -> None:
    meta = {
        "id": kernel_id,
        "title": title,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": True,
        "dataset_sources": ["merouanefaik/slm-benchmark-baseline"],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


write_notebook(
    ROOT / "qwen15" / "baseline_benchmark_smoke.ipynb",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "smoke_test",
)
write_notebook(
    ROOT / "qwen15" / "baseline_benchmark_full.ipynb",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "full",
)
write_metadata(
    ROOT / "qwen15" / "kernel-metadata.json",
    "merouanefaik/slm-benchmark-qwen15-kaggle",
    "SLM Benchmark Qwen15 Kaggle",
    "baseline_benchmark_smoke.ipynb",
)

write_notebook(
    ROOT / "qwen3" / "baseline_benchmark_full.ipynb",
    "Qwen/Qwen2.5-Coder-3B-Instruct",
    "full",
)
write_metadata(
    ROOT / "qwen3" / "kernel-metadata.json",
    "merouanefaik/slm-benchmark-qwen3-kaggle",
    "SLM Benchmark Qwen3 Kaggle",
    "baseline_benchmark_full.ipynb",
)

print("Prepared notebooks under", ROOT)
