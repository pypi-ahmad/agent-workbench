# Threat model

This document defines the security boundaries, risks, and mitigations implemented in Agent Workbench.

## 1. Zero-shell policy

### Threat
An agent could invoke arbitrary system binaries, execute batch scripts, or run shell interpreters (`cmd.exe`, `powershell.exe`, `bash`) to compromise the host system.

### Mitigation
- No subprocess calls exist in the codebase.
- No shell execution tools or terminal bridges are registered or exposed to the model.
- Neither Docker containers nor WSL2 subsystems are used.
- All tools execute pure Python logic strictly inside the existing process.

## 2. Filesystem sandbox

### Threat
An agent could read sensitive files outside the project (such as `.env`, user SSH keys, or system directories) through relative path traversal (`../`) or absolute paths.

### Mitigation
- The `workspace/` directory inside the repository serves as the single filesystem root for file tools (`list_dir`, `read_file`, `write_note`).
- Path resolution in `resolve_in_workspace()` verifies that every target path resolves to a location within `workspace/`.
- Traversal attempts above `workspace/` raise a `PermissionError` and return an access denied message to the agent.
- Character outputs for `read_file` are capped at 10,000 characters to prevent token exhaustion.

## 3. Math expression evaluation

### Threat
A calculator tool using Python's `eval()` or `exec()` can execute arbitrary code through string injection, imports, or dunder method introspection (such as `__subclasses__()`).

### Mitigation
- The `calc` tool uses Python's Abstract Syntax Tree (`ast.parse`) in `eval` mode.
- Only a whitelist of AST node types is supported: `ast.Constant`, `ast.BinOp`, `ast.UnaryOp`, `ast.Name`, and `ast.Call`.
- Allowed operators are limited to basic arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`).
- Exponents above 1000 are rejected to prevent CPU denial of service.
- Function calls are restricted to a fixed map of safe math functions (`sqrt`, `abs`, `round`, `sin`, `cos`, `log`, etc.).
- Attribute lookups (`ast.Attribute`), assignments, imports, and dunder names are rejected.

## 4. Outbound network requests

### Threat
An agent could execute Server-Side Request Forgery (SSRF) to scan internal subnets, contact cloud metadata services (`169.254.169.254`), or exfiltrate local data to untrusted endpoints.

### Mitigation
- The `http_get` tool enforces HTTPS only. Plain HTTP requests are rejected immediately.
- Requests validate the destination hostname against `DEFAULT_ALLOWLIST` (including `api.github.com`, `httpbin.org`, `wttr.in`, `dummyjson.com`).
- Any destination not in the allowlist is blocked before network transmission.
- Request timeouts default to 10 seconds (maximum 30 seconds), and response bodies are capped at 8,000 characters.

## 5. Credential handling

### Threat
API keys (such as `AGNESAI_API_KEY`) could be logged to disk, printed to stdout, written into git commits, or sent to models in tool arguments.

### Mitigation
- Keys are loaded from the user environment or `.env` file at runtime.
- The `.gitignore` file excludes `.env`, `.venv`, and Streamlit secrets.
- Status checks test only whether an environment variable exists, returning a boolean presence flag rather than the secret string.
- The example file `.env.example` lists variable names without values.
