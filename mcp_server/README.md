# MCP lecture seule — S3 (stdio, stdlib, sans SDK pour coût 0 et compat FastAPI 0.115)

Lance : `python -m mcp_server.server` (JSON-RPC sur stdin/stdout).
Outils : `list_files`, `read_file`, `search_symbols` uniquement.
Sécurité : dossier projet seul, `../` et absolus refusés, secrets `redact()`, aucune écriture/shell.
