"""Serveur MCP lecture seule (stdio, stdlib uniquement, sans SDK).

Protocole JSON-RPC minimal compatible MCP :
  {"jsonrpc":"2.0","id":1,"method":"initialize"}
  {"jsonrpc":"2.0","id":2,"method":"tools/list"}
  {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"..."}}}

Outils autorisés uniquement : list_files, read_file, search_symbols.
Aucune écriture, aucun shell, dossier projet seul, `../` refusé, secrets filtrés.
Usage : python -m mcp_server.server
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents import tools as agent_tools

ALLOWED_TOOLS = ["list_files", "read_file", "search_symbols"]
DEFAULT_PATTERN = "evals/tasks/**/*.py"
MAX_FILES = 50
MAX_CHARS = 20000


def list_files(pattern: str = DEFAULT_PATTERN, limit: int = MAX_FILES) -> list[str]:
    if ".." in pattern.replace("\\", "/"):
        raise ValueError("Traversée de chemin interdite ('..').")
    if pattern.startswith("/") or (len(pattern) > 1 and pattern[1] == ":"):
        raise ValueError("Chemin absolu refusé.")
    files = sorted(str(p.relative_to(agent_tools.PROJECT_ROOT.resolve())).replace("\\", "/")
                   for p in agent_tools.PROJECT_ROOT.glob(pattern) if p.is_file())
    return files[: max(1, min(limit, MAX_FILES))]


def read_file(path: str) -> str:
    text = agent_tools.read_file(path, max_chars=MAX_CHARS)
    return agent_tools.redact(text)


def search_symbols(path: str) -> dict:
    text = agent_tools.read_file(path, max_chars=MAX_CHARS)
    return agent_tools.search_symbols(text)


def _tools_spec() -> list[dict]:
    return [
        {"name": "list_files", "description": "Liste fichiers relatifs (glob read-only)",
         "inputSchema": {"type": "object", "properties": {
             "pattern": {"type": "string"}, "limit": {"type": "integer"}}, "required": []}},
        {"name": "read_file", "description": "Lit un fichier relatif (../ refusé, secrets filtrés)",
         "inputSchema": {"type": "object", "properties": {
             "path": {"type": "string"}}, "required": ["path"]}},
        {"name": "search_symbols", "description": "Fonctions/classes/imports via AST (sans exécution)",
         "inputSchema": {"type": "object", "properties": {
             "path": {"type": "string"}}, "required": ["path"]}},
    ]


def handle_message(msg: dict) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method", "")

    def ok(result: object) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    try:
        if method == "initialize":
            return ok({"protocolVersion": "2024-11-05", "serverInfo": {"name": "slm-readonly", "version": "0.3.0-s3"}})
        if method == "tools/list":
            return ok({"tools": _tools_spec()})
        if method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            if name not in ALLOWED_TOOLS:
                return err(-32601, f"Outil non autorisé: {name} (allow-list: {ALLOWED_TOOLS})")
            if name == "list_files":
                return ok({"files": list_files(str(args.get("pattern", DEFAULT_PATTERN)),
                                               int(args.get("limit", MAX_FILES)) )})
            if name == "read_file":
                return ok({"path": args.get("path", ""), "content": read_file(str(args.get("path", "")))})
            if name == "search_symbols":
                return ok({"path": args.get("path", ""), "symbols": search_symbols(str(args.get("path", "")))})
            return err(-32601, f"Outil inconnu: {name}")
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        return err(-32601, f"Méthode inconnue: {method}")
    except ValueError as exc:
        return err(-32602, str(exc))
    except Exception as exc:  # noqa: BLE001 - jamais de crash stdio
        return err(-32603, agent_tools.redact(str(exc))[:500])


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "JSON invalide"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
