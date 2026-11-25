"""Merge downloaded benchmark result ZIPs locally on Windows. No cloud access.

The notebooks export a ZIP whose top level is ``results/``:

    results/
    +-- smoke_test/qwen15/<RUN_ID>/...
    +-- baseline/qwen3/<RUN_ID>/...      # MODE="full" writes here
    +-- metadata/run_<RUN_ID>.json
    +-- SHA256SUMS.txt

This script unions several unzipped ``results/`` trees into one merged tree
without overwriting a run directory with different content. Example
(PowerShell):

    $base = "$env:USERPROFILE\\Downloads\\slm-benchmark"
    python benchmark\\scripts\\merge_results.py `
      --source "$base\\session-01\\results" `
      --source "$base\\session-02\\results" `
      --dest "$base\\merged\\results"

Each source is hash-verified against its own ``SHA256SUMS.txt`` before
merging (unless --skip-verify is given). A destination run directory that
already exists with byte-identical content is skipped; a destination that
exists with different content raises an error (never overwrite silently).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source(source_root: Path) -> tuple[list[str], list[str]]:
    """Verify every file listed in <source>/SHA256SUMS.txt. Raises on mismatch."""
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[str] = []

    sums_candidates = [source_root / "SHA256SUMS.txt", source_root / "metadata" / "SHA256SUMS.txt"]
    sums_path = next((p for p in sums_candidates if p.is_file()), None)
    if sums_path is None:
        warnings.append("No SHA256SUMS.txt found; skipping per-file verification.")
        return checked, warnings

    base = source_root
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"Malformed SHA256SUMS line: {line!r}")
            continue
        expected, rel = parts
        # rel paths are stored relative to RESULTS_ROOT (results/)
        path = base.joinpath(*rel.split("/")) if rel else None
        if path is None or not path.is_file():
            # Fallback: relative to the sums file's enclosing dir.
            alt = sums_path.parent.joinpath(*rel.split("/"))
            if alt.is_file():
                path = alt
        if path is None or not path.is_file():
            errors.append(f"Missing file listed in SHA256SUMS: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"Hash mismatch for {rel}: expected {expected}, got {actual}")
        else:
            checked.append(rel)
    if errors:
        raise ValueError("SHA256 verification failed for " + str(source_root) + ": " + "; ".join(errors))
    return checked, warnings


def files_identical(a_file: Path, b_file: Path) -> bool:
    return a_file.is_file() and b_file.is_file() and sha256_file(a_file) == sha256_file(b_file)


def dirs_identical(src: Path, dst: Path) -> bool:
    """True if every file in src exists in dst with the same bytes (extra files in dst ignored)."""
    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(src)
            dst_file = dst / rel
            if not files_identical(src_file, dst_file):
                return False
    return True


MODEL_DIRS = ("qwen15", "qwen3", "phi4mini")
MODES = ("smoke_test", "baseline")


def merge_tree(src: Path, dst: Path) -> list[str]:
    """Union-copy src into dst, never overwriting different content. Returns actions."""
    actions: list[str] = []
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    # Handle run directories atomically: only <mode>/<model>/<RUN_ID> dirs
    # are atomic units. Intermediate dirs (baseline/, qwen15/) are allowed
    # to gain new RUN_ID subdirectories, so they are not checked as a whole.
    for src_dir in sorted(p for p in src.rglob("*") if p.is_dir()):
        rel_dir = src_dir.relative_to(src)
        parts = rel_dir.parts
        if not (len(parts) == 3 and parts[0] in MODES and parts[1] in MODEL_DIRS):
            continue
        dst_dir = dst / rel_dir
        if dst_dir.exists() and any(dst_dir.iterdir()):
            if not dirs_identical(src_dir, dst_dir):
                raise RuntimeError(
                    f"Refusing to overwrite different content at {dst_dir} "
                    f"(from {src_dir}). Unzip to a fresh --dest or remove the old folder manually."
                )
            actions.append(f"skip (identical): {rel_dir}")

    for src_file in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = src_file.relative_to(src)
        # SHA256SUMS.txt at the top level is regenerated per source; the merged
        # tree keeps per-run copies but a single merged sums file is written at
        # the end by the caller, so skip the root-level sums file here.
        if rel.as_posix() in ("SHA256SUMS.txt", "metadata/SHA256SUMS.txt"):
            continue
        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        if dst_file.exists():
            if files_identical(src_file, dst_file):
                actions.append(f"skip (identical): {rel.as_posix()}")
                continue
            raise RuntimeError(
                f"Refusing to overwrite different file {dst_file} with {src_file}. "
                "Merging must be a union of run directories; investigate manually."
            )
        shutil.copy2(src_file, dst_file)
        actions.append(f"copy: {rel.as_posix()}")
    return actions


def write_merged_sums(dest: Path) -> Path:
    out = dest / "SHA256SUMS.txt"
    entries = {}
    for path in sorted(p for p in dest.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        rel = path.relative_to(dest).as_posix()
        entries[rel] = sha256_file(path)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        for rel in sorted(entries):
            handle.write(f"{entries[rel]}  {rel}\n")
    (dest / "metadata").mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, dest / "metadata" / "SHA256SUMS.txt")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True,
                        help="Unzipped results/ directory from one session (repeatable).")
    parser.add_argument("--dest", required=True, help="Merged results/ directory.")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip SHA256 verification of each source.")
    args = parser.parse_args()

    dest = Path(args.dest)
    all_actions: list[str] = []
    for raw in args.source:
        src = Path(raw)
        # Accept both the results/ folder itself and a folder containing results/.
        if not (src / "smoke_test").exists() and not (src / "baseline").exists():
            if (src / "results" / "baseline").exists():
                src = src / "results"
            else:
                print(f"WARNING: {src} has no smoke_test/ or baseline/; merging empty tree.", file=sys.stderr)
        if not args.skip_verify:
            try:
                checked, warnings = verify_source(src)
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
            for w in warnings:
                print(f"  WARN: {w}")
            print(f"Verified {src}: {len(checked)} files")
        try:
            actions = merge_tree(src, dest)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        all_actions.extend(f"[{src}] {a}" for a in actions)
        print(f"Merged {src} -> {dest} ({len(actions)} actions)")

    sums = write_merged_sums(dest)
    print(f"Wrote merged {sums}")
    print(f"Done. Merged tree: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
