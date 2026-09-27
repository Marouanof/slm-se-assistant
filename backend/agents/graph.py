"""Graphe LangGraph S2 — noeuds déterministes (sans LLM)."""

import tempfile
import time
from pathlib import Path

from langgraph.graph import END, StateGraph

from backend.agents import tools
from backend.agents.state import AgentState

PROMPT_VERSION = "v1"
MODEL_ID = "template-s2"

_BANDIT_HINTS = {
    "B102": ("exec/eval détecté — risque d'injection de code", "Remplacer exec/eval par ast.literal_eval ou refactor sans exécution dynamique."),
    "B301": ("pickle.loads détecté — désérialisation non sûre", "Remplacer pickle par json ou valider la source, ne jamais charger de données non fiables."),
    "B302": ("marshal/loads détecté — désérialisation non sûre", "Éviter marshal sur données externes."),
    "B602": ("shell=True détecté — injection shell possible", "Passer shell=False avec argv liste, valider les entrées."),
    "B603": ("subprocess sans shell — vérifier les entrées", "Valider les arguments, préférer allow-list de commandes."),
    "B404": ("import subprocess — usage à contrôler", "Restreindre aux commandes autorisées, timeout + sandbox."),
    "B105": ("mot de passe en dur détecté", "Externaliser le secret en variable d'environnement, filtrer des logs."),
    "B106": ("fonction avec mot de passe en dur", "Externaliser le secret, ne pas committer."),
    "B107": ("mot de passe en dur dans fonction", "Externaliser le secret en variable d'environnement."),
    "B108": ("fichier temporaire insécurisé", "Utiliser tempfile.TemporaryDirectory/mkstemp avec permissions restreintes."),
}


def _traj(state: AgentState, step: str) -> list[str]:
    return [*state.get("trajectoire", []), step]


def node_analyse(state: AgentState) -> dict:
    try:
        code = state.get("input_code")
        path = state.get("input_path")
        if code is not None:
            with tempfile.TemporaryDirectory() as td:
                target = Path(td) / "snippet.py"
                target.write_text(code, encoding="utf-8")
                ruff = tools._run_ruff(target)
                bandit = tools._run_bandit(target)
            files = ["snippet.py"]
            code_len = len(code)
            tokens_in = tools.count_tokens(code)
        elif path is not None:
            target = tools.resolve_project_path(path)  # lève 422/404 si invalide
            ruff = tools._run_ruff(target)
            bandit = tools._run_bandit(target)
            code = target.read_text(encoding="utf-8", errors="replace")
            files = [str(target.relative_to(tools.PROJECT_ROOT.resolve()))]
            code_len = len(code)
            tokens_in = tools.count_tokens(code)
        else:
            return {"trajectoire": _traj(state, "analyse:error"), "status": "error"}
        symbols = tools.search_symbols(code or "")
        return {
            "files": files,
            "code_len": code_len,
            "ruff": ruff,
            "bandit": bandit,
            "symbols": symbols,
            "tokens_in": tokens_in,
            "trajectoire": _traj(state, "analyse"),
            "status": "ok",
        }
    except Exception as exc:  # noqa: BLE001 - ne jamais crasher le graphe sauf HTTP
        from fastapi import HTTPException as _HTTP

        if isinstance(exc, _HTTP):
            raise
        return {"trajectoire": _traj(state, "analyse:error"), "status": "error",
                "tests_output": tools.redact(str(exc))[:500]}


def node_tests(state: AgentState) -> dict:
    try:
        code = state.get("input_code")
        path = state.get("input_path")
        if code is not None:
            res = tools.run_pytest_tmp(code)
        elif path is not None:
            res = tools.run_pytest_path(path)
            code = res.get("code", "")
        else:
            return {"trajectoire": _traj(state, "tests:error"), "status": "error"}
        return {
            "tests_pass": res["tests_pass"],
            "coverage_pct": res.get("coverage_pct"),
            "tests_output": res.get("output", "")[:2000],
            "tokens_out": tools.count_tokens(res.get("output", "")),
            "trajectoire": _traj(state, "tests"),
            "status": "ok",
        }
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException as _HTTP

        if isinstance(exc, _HTTP):
            raise
        return {"trajectoire": _traj(state, "tests:error"), "status": "error",
                "tests_pass": False, "tests_output": tools.redact(str(exc))[:500]}


def node_revue(state: AgentState) -> dict:
    findings: list[str] = []
    patches: list[str] = []
    for b in state.get("bandit", []):
        tid = str(b.get("test_id", ""))
        hint = _BANDIT_HINTS.get(tid)
        if hint:
            findings.append(f"[bloquant:{tid}] {hint[0]}")
            patches.append(f"- {tid}: {hint[1]}")
        elif tid and tid not in ("BANDIT_ERROR", "BANDIT_TIMEOUT"):
            findings.append(f"[bandit:{tid}] {b.get('text', '')}")
    for r in state.get("ruff", []):
        code = str(r.get("code", ""))
        if code.startswith("E9") or code in ("F821", "F822"):
            findings.append(f"[bloquant:{code}] {r.get('message', '')}")
        elif code and code not in ("RUFF_ERROR", "RUFF_TIMEOUT"):
            findings.append(f"[ruff:{code}] {r.get('message', '')}")
    if state.get("tests_pass") is False:
        findings.append("[tests] smoke pytest échoué — voir tests_output")
        patches.append("- Corriger l'erreur smoke avant revue (import/compile).")
    if not findings:
        findings.append("[ok] aucun défaut bloquant détecté (Ruff+Bandit+smoke verts)")
    patch_proposal = "\n".join(patches) if patches else "Aucun correctif requis."
    return {
        "findings": findings,
        "patch_proposal": patch_proposal,
        "trajectoire": _traj(state, "revue"),
        "status": "ok",
    }


def node_humain(state: AgentState) -> dict:
    return {
        "model": MODEL_ID,
        "prompt_version": PROMPT_VERSION,
        "trajectoire": _traj(state, "humain"),
        "status": "needs_review",
    }


def build_graph():  # type: ignore[no-untyped-def]
    """Construit le graphe Analyse → Tests → Revue → Humain."""
    g = StateGraph(AgentState)
    g.add_node("analyse", node_analyse)
    g.add_node("tests", node_tests)
    g.add_node("revue", node_revue)
    g.add_node("humain", node_humain)
    g.set_entry_point("analyse")
    g.add_edge("analyse", "tests")
    g.add_edge("tests", "revue")
    g.add_edge("revue", "humain")
    g.add_edge("humain", END)
    return g.compile()


_GRAPH = None


def get_graph():  # type: ignore[no-untyped-def]
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_pipeline(code: str | None = None, path: str | None = None) -> dict:
    """Exécute le pipeline complet, mesure la latence. Lève HTTPException si path invalide."""
    started = time.perf_counter()
    initial: AgentState = {
        "input_code": code,
        "input_path": path,
        "trajectoire": [],
        "model": MODEL_ID,
        "prompt_version": PROMPT_VERSION,
        "status": "ok",
    }
    result = dict(get_graph().invoke(initial))
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    result["model"] = MODEL_ID
    result["prompt_version"] = PROMPT_VERSION
    if result.get("status") != "error":
        result["status"] = "needs_review"
    return result
