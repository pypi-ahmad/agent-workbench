# Threat model

## Filesystem boundary

All file tools resolve paths against this repository's `workspace/` directory.
They reject `..`, reject absolute paths outside the workspace, and verify the
resolved path remains under the workspace after path resolution. `read_file`
accepts UTF-8 text up to 64 KiB. `write_note` writes only under
`workspace/notes/` and accepts a simple filename without slashes, drive
letters, traversal segments, or Windows reserved device names.

## Code execution

No tool invokes a shell, subprocess, `eval`, or `exec`. The calculator walks a
restricted Python AST and accepts only numbers, parentheses, and
`+ - * / **`. Names, attributes, imports, and function calls fail closed.

## Network boundary

`http_get` accepts HTTPS only. The default allowlist in `src/config.py` contains
only `example.com` and `httpbin.org`. It blocks credentials in URLs, localhost,
IP literals, `file://`, plain HTTP, and every unlisted host before making a
request. Redirect following is disabled so an allowed host cannot redirect the
request to another host. Returned response text is capped at 4,000 characters.

## Credential boundary

The Agnes client reads `AGNESAI_API_KEY` from the current process environment.
The key is not written to files, logs, Streamlit state, or trace exports.
`.env` and `.venv/` are ignored by Git. The app does not load credentials from
`.env`.

## Out of scope

The application has no subprocess or shell tool, file deletion tool, OCR, PDF
parser, vector database, Docker integration, or WSL2 integration.
