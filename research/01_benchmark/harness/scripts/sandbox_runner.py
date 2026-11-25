"""Isolated code-execution sandbox for the SE benchmark.

Executes model-generated Python against the hidden reference tests in a
subprocess with hard time/memory/process limits. Never runs in the host
interpreter.

Design goals
------------
- No network, no host filesystem writes beyond a temp file we delete.
- Hard timeout (CPU + wall) so infinite loops cannot hang the run.
- Memory cap so a generated `range(10**12)` list cannot OOM the session.
- Static pre-check rejects obviously dangerous imports/calls (defence in depth).
- Deterministic: same program -> same verdict.

This module is CPU-only. It does not need a GPU and runs on Windows (local
sanity checks) and Linux (Kaggle) alike. `resource` limits are applied only on
POSIX; on Windows only the wall-clock timeout is enforced.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from typing import Any

# Generated code often contains regex strings such as "\d" or "\." that the
# compiler flags with SyntaxWarning while we only parse it for safety checks.
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Modules that can escape the sandbox or touch the host. The reference tests
# themselves need numpy/math/typing, so this is a targeted blacklist rather
# than a whitelist.
_FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "ctypes",
    "multiprocessing", "threading", "signal", "resource", "importlib",
    "builtins", "__builtin__", "pickle", "marshal", "shelve", "sqlite3",
    "http", "urllib", "requests", "ftplib", "telnetlib", "smtplib",
    "asyncio", "concurrent", "pty", "tty", "termios", "fcntl", "mmap",
    "gc", "inspect", "code", "codeop", "compileall", "py_compile",
    "webbrowser", "distutils", "setuptools", "pip", "ensurepip",
    "venv", "platform", "getpass", "pwd", "grp", "crypt", "nis",
}

_FORBIDDEN_CALLS = {"eval", "exec", "__import__", "compile", "open", "input", "breakpoint"}

_DEFAULT_TIMEOUT = 10
_DEFAULT_MEMORY_MB = 2048
_DEFAULT_MAX_PROCS = 16
_DEFAULT_MAX_FSIZE_MB = 16


def static_safety_check(code: str) -> tuple[bool, str]:
    """Return (safe, reason). Rejects unparsable or dangerous code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False, "syntax_error"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _FORBIDDEN_MODULES:
                    return False, f"forbidden_import:{root}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _FORBIDDEN_MODULES:
                return False, f"forbidden_import:{root}"
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _FORBIDDEN_CALLS:
                return False, f"forbidden_call:{fn.id}"
            if isinstance(fn, ast.Attribute) and fn.attr in _FORBIDDEN_CALLS:
                return False, f"forbidden_call:{fn.attr}"
    return True, "ok"


def _preexec_limits(timeout: int, memory_mb: int, max_procs: int, max_fsize_mb: int):
    """Return a POSIX preexec_fn that applies hard rlimits, or None on Windows."""
    if os.name != "posix":
        return None

    def _apply():  # pragma: no cover (only exercised on Linux)
        import resource

        cpu = int(timeout) + 2
        mem = int(memory_mb) * 1024 * 1024
        fsize = int(max_fsize_mb) * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (max_procs, max_procs))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, OSError):
            pass

    return _apply


def run_python(
    program: str,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    memory_mb: int = _DEFAULT_MEMORY_MB,
    max_procs: int = _DEFAULT_MAX_PROCS,
    max_fsize_mb: int = _DEFAULT_MAX_FSIZE_MB,
) -> dict[str, Any]:
    """Execute `program` in an isolated subprocess and return a verdict dict.

    Keys: executed, timed_out, returncode, passed, stdout_tail, stderr_tail.
    `passed` is True iff the process exits 0 (no uncaught exception).
    """
    tmp_path = None
    try:
        if program.count("\x00"):  # defensive: NUL bytes break exec
            return _verdict(False, False, None, False, "", "program_contains_nul_byte")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(program)
            tmp_path = fh.name

        cmd = [sys.executable, "-I", tmp_path]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5,  # wall clock guard above the CPU rlimit
                preexec_fn=_preexec_limits(timeout, memory_mb, max_procs, max_fsize_mb),
                env={"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"},
                cwd=tempfile.gettempdir(),
            )
            return _verdict(
                executed=True,
                timed_out=False,
                returncode=proc.returncode,
                passed=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return _verdict(False, True, None, False, "", "wall_clock_timeout")
    except Exception as exc:  # pragma: no cover - defensive
        return _verdict(False, False, None, False, "", f"sandbox_error:{type(exc).__name__}:{exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _verdict(executed, timed_out, returncode, passed, stdout, stderr) -> dict[str, Any]:
    return {
        "executed": bool(executed),
        "timed_out": bool(timed_out),
        "returncode": returncode,
        "passed": bool(passed),
        "stdout_tail": (stdout or "")[-2000:],
        "stderr_tail": (stderr or "")[-2000:],
    }


# ---------------------------------------------------------------------------
# Test-program builders (one per task)
# ---------------------------------------------------------------------------

def _humaneval_program(generated_code: str, test_script: str, entry_point: str) -> str:
    # HumanEval+ ships `def check(candidate)` and never calls it; we append the call.
    return (
        generated_code.rstrip()
        + "\n\n"
        + test_script.strip()
        + "\n\n"
        + f"check({entry_point})\n"
    )


def _mbpp_program(generated_code: str, test_script: str) -> str:
    # MBPP+ test scripts run their assertion loop at import time.
    return generated_code.rstrip() + "\n\n" + test_script.strip() + "\n"


# Minimal pytest compatibility layer so generated tests that use
# `pytest.raises(...)` run even when pytest is not installed.
_PYTEST_STUB = r'''
import sys as _sb_sys, types as _sb_types
try:
    import pytest as _sb_pytest  # noqa: F401
except Exception:
    _sb_stub = _sb_types.ModuleType("pytest")
    class _SbRaises:
        def __init__(self, expected):
            self.expected = expected
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                raise AssertionError("DID NOT RAISE " + repr(self.expected))
            return issubclass(exc_type, self.expected)
    _sb_stub.raises = _SbRaises
    _sb_sys.modules["pytest"] = _sb_stub
'''

# Invoke `def test_*()` functions; top-level `assert` statements already ran on
# import. Without this, function-style tests are defined but never executed and
# wrongly count as passing.
_TEST_RUNNER = r'''
def _sb_run_generated_tests():
    import unittest as _sb_unittest
    ns = globals()
    ran = 0
    # unittest.TestCase subclasses
    for _obj in list(ns.values()):
        if isinstance(_obj, type) and issubclass(_obj, _sb_unittest.TestCase):
            suite = _sb_unittest.defaultTestLoader.loadTestsFromTestCase(_obj)
            result = _sb_unittest.TextTestRunner(verbosity=0).run(suite)
            ran += result.testsRun
            if not result.wasSuccessful():
                raise AssertionError("unittest failures")
    # plain test functions
    for _name, _fn in list(ns.items()):
        if _name.startswith("test") and callable(_fn) and _fn.__module__ == "__main__":
            _fn()
            ran += 1
    print("SANDBOX_TESTS_RAN", ran)

_sb_run_generated_tests()
'''

def run_code_generation(generated_code: str, reference_tests: dict, **limits) -> dict[str, Any]:
    entry = reference_tests.get("entry_point") or "solution"
    kind = reference_tests.get("kind", "")
    test_script = reference_tests.get("test", "")
    if kind == "humaneval_plus":
        program = _humaneval_program(generated_code, test_script, entry)
    else:
        program = _mbpp_program(generated_code, test_script)
    safe, reason = static_safety_check(program)
    if not safe:
        return {"pass@1": 0.0, "reason": reason, **_verdict(False, False, None, False, "", reason)}
    verdict = run_python(program, **limits)
    return {"pass@1": 1.0 if verdict["passed"] else 0.0, "reason": "ok", **verdict}


def run_code_refactoring(refactored_code: str, reference_tests: dict, **limits) -> dict[str, Any]:
    entry = reference_tests.get("entry_point") or "solution"
    kind = reference_tests.get("kind", "")
    test_script = reference_tests.get("test", "")
    if kind == "humaneval_plus":
        program = _humaneval_program(refactored_code, test_script, entry)
    else:
        program = _mbpp_program(refactored_code, test_script)
    safe, reason = static_safety_check(program)
    if not safe:
        return {"pass@1": 0.0, "reason": reason, **_verdict(False, False, None, False, "", reason)}
    verdict = run_python(program, **limits)
    return {"pass@1": 1.0 if verdict["passed"] else 0.0, "reason": "ok", **verdict}


def run_unit_tests(
    generated_tests: str,
    canonical_solution: str,
    reference_tests: dict,
    mutants: list | None = None,
    **limits,
) -> dict[str, Any]:
    """Evaluate generated tests against the canonical solution and mutants.

    - `tests_pass_on_canonical`: generated tests must pass on correct code.
    - `mutation_kill_rate`: fraction of mutants the generated tests reject.

    The generated tests REPLACE the reference tests: they must accept the
    canonical solution and reject mutants. We therefore run
    `canonical_solution + generated_tests` (no reference assertion loop).
    """
    # Reject outputs that contain no test at all (empty, prose, or a lone
    # function definition). Otherwise they would "pass" without testing anything.
    if (
        not re.search(r"\bassert\b", generated_tests)
        and not re.search(r"\bdef\s+test\w*\s*\(", generated_tests)
        and "unittest" not in generated_tests
    ):
        return {
            "tests_pass_on_canonical": 0.0,
            "mutation_kill_rate": None,
            "n_mutants": 0,
            "mutants_killed": 0,
            "reason": "no_tests_found",
            **_verdict(False, False, None, False, "", "no_tests_found"),
        }

    # Static-check only the untrusted generated tests. The canonical solution,
    # pytest shim and test runner are trusted harness code.
    safe, reason = static_safety_check(generated_tests)
    if not safe:
        return {
            "tests_pass_on_canonical": 0.0,
            "mutation_kill_rate": None,
            "n_mutants": 0,
            "mutants_killed": 0,
            "reason": reason,
            **_verdict(False, False, None, False, "", reason),
        }

    # Prepend a pytest shim (some tests call `import pytest`) and append a
    # runner that actually invokes `def test_*()` functions. Without the runner,
    # function-style tests are only *defined* and never run.
    program = (
        _PYTEST_STUB
        + canonical_solution.rstrip()
        + "\n\n"
        + generated_tests.strip()
        + "\n"
        + _TEST_RUNNER
    )
    base = run_python(program, **limits)
    pass_on_canonical = 1.0 if base["passed"] else 0.0

    kill_rate = None
    n_mutants = 0
    killed = 0
    if mutants:
        for mutant in mutants:
            code = mutant.get("code")
            if not code:
                continue
            n_mutants += 1
            prog = (
                _PYTEST_STUB
                + code.rstrip()
                + "\n\n"
                + generated_tests.strip()
                + "\n"
                + _TEST_RUNNER
            )
            v = run_python(prog, **limits)
            # A mutant is "killed" when the generated tests make it fail.
            if not v["passed"]:
                killed += 1
        if n_mutants:
            kill_rate = killed / n_mutants

    return {
        "tests_pass_on_canonical": pass_on_canonical,
        "mutation_kill_rate": kill_rate,
        "n_mutants": n_mutants,
        "mutants_killed": killed,
        "reason": reason,
        **base,
    }


if __name__ == "__main__":  # tiny self-test
    ok, why = static_safety_check("import os\nos.system('echo hi')")
    assert not ok, why
    v = run_python("print('hello'); assert 1+1==2")
    assert v["passed"], v
    v = run_python("import time\ntime.sleep(30)", timeout=1)
    assert v["timed_out"], v
    print("sandbox self-test OK")