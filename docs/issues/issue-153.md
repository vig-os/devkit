---
type: issue
state: closed
created: 2026-02-22T09:21:10Z
updated: 2026-06-23T06:56:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/153
comments: 4
labels: feature, area:workspace, effort:small, semver:minor
assignees: gerchowl
milestone: none
projects: none
parent: 70
children: none
synced: 2026-06-23T08:02:57.490Z
---

# [Issue 153]: [[FEATURE] devc_remote_uri.py — Cursor URI construction for remote devcontainers](https://github.com/vig-os/devcontainer/issues/153)

### Description

Create `scripts/devc_remote_uri.py` — a standalone Python module/CLI that builds the Cursor/VS Code nested authority URI for remote devcontainers. Called by `devc-remote.sh` (sibling sub-issue).

### Problem Statement

Part of #70. Opening Cursor/VS Code into a remote devcontainer requires constructing a `vscode-remote://` URI with hex-encoded JSON specs. Bash is brittle for JSON serialization and hex encoding — Python handles this cleanly with stdlib only.

### Proposed Solution

A Python script with:

- `hex_encode(s: str) -> str` — `s.encode().hex()`
- `build_uri(workspace_path, devcontainer_path, ssh_host, container_workspace) -> str` — assembles `vscode-remote://dev-container+{dc_hex}@ssh-remote+{ssh_host}{container_workspace}`
- CLI interface: `devc_remote_uri.py <workspace_path> <ssh_host> <container_workspace>` — reads `devcontainerPath` from args, prints URI to stdout
- No external dependencies (stdlib only: `json`, `sys`, `argparse`)

#### URI format

```
vscode-remote://dev-container+{DC_HEX}@ssh-remote+{SSH_SPEC}/{container_workspace}
```

Where `DC_HEX` is the hex-encoded JSON:
```json
{"settingType":"config","workspacePath":"/home/user/repo","devcontainerPath":"/home/user/repo/.devcontainer/devcontainer.json"}
```

SSH spec — two variants:
- **Simple** (host from `~/.ssh/config`): `@ssh-remote+loginnode`
- **Full** (hex-encoded JSON): `@ssh-remote+{SSH_HEX}` where `{"hostName":"user@1.2.3.4 -p 22"}`

### Files

- Create: `scripts/devc_remote_uri.py`
- Create: `tests/test_devc_remote_uri.py`

### Testing Strategy

Pytest unit tests:
- `hex_encode()`: known input → exact hex output
- `build_uri()`: known inputs → exact URI matching Cursor docs examples
- CLI: subprocess call with args, verify stdout
- Edge cases: special chars in paths, spaces in host names
- Error cases: missing args, empty strings

Verify: `uv run pytest tests/test_devc_remote_uri.py -v`

### Alternatives Considered

- Pure bash hex encoding (`od -A n -t x1 | tr -d '[\n\t ]'`): works but fragile across platforms
- Node.js helper: rejected — Python already available in devcontainer

### Impact

- New file, no changes to existing behavior
- Backward compatible
- Standalone module — can be worked in parallel with the sibling bash script sub-issue

### Changelog Category

Added
---

# [Comment #1]() by [gerchowl]()

_Posted on February 22, 2026 at 09:42 AM_

## Design

**Architecture**

Single standalone module `scripts/devc_remote_uri.py` with:
- Pure functions `hex_encode()` and `build_uri()` — no side effects, easy to unit test
- CLI entry point via `argparse` — positional args: `workspace_path`, `ssh_host`, `container_workspace`; `devcontainer_path` as optional (default: `{workspace_path}/.devcontainer/devcontainer.json`)
- Stdlib only: `json`, `sys`, `argparse`

**URI construction**

- `hex_encode(s)` → `s.encode().hex()` (UTF-8)
- Dev-container spec JSON: `{"settingType":"config","workspacePath":"<path>","devcontainerPath":"<path>"}` → hex-encoded
- URI format: `vscode-remote://dev-container+{DC_HEX}@ssh-remote+{SSH_SPEC}/{container_workspace}`
- SSH spec: simple host name (e.g. `loginnode`) passed through as-is; full hex variant deferred to sibling sub-issue if needed (YAGNI)

**Error handling**

- `argparse` for missing required args → exit 2 with usage
- Empty strings → raise `ValueError` with clear message
- No network or filesystem I/O — pure string transformation

**Testing**

- `test_devc_remote_uri.py`: pytest unit tests per issue spec
- `hex_encode`: known input → exact hex output
- `build_uri`: known inputs → exact URI (match Cursor docs examples)
- CLI: subprocess call with args, assert stdout
- Edge cases: special chars in paths, spaces
- Error cases: missing args, empty strings

---

# [Comment #2]() by [gerchowl]()

_Posted on February 22, 2026 at 09:42 AM_

## Implementation Plan

Issue: #153
Branch: feature/153-devc-remote-uri-py

### Tasks

- [x] Task 1: Add test_devc_remote_uri.py with hex_encode tests (known input → exact hex) — `tests/test_devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v -k hex_encode`
- [x] Task 2: Implement hex_encode() in devc_remote_uri.py — `scripts/devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v -k hex_encode`
- [x] Task 3: Add build_uri tests (known inputs → exact URI per Cursor docs) — `tests/test_devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v -k build_uri`
- [x] Task 4: Implement build_uri() — `scripts/devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v -k build_uri`
- [x] Task 5: Add CLI tests (subprocess, stdout, error cases) — `tests/test_devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v -k cli`
- [x] Task 6: Implement CLI with argparse — `scripts/devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v`
- [x] Task 7: Add edge-case tests (special chars, spaces, empty strings) — `tests/test_devc_remote_uri.py` — verify: `uv run pytest tests/test_devc_remote_uri.py -v`

---

# [Comment #3]() by [gerchowl]()

_Posted on February 22, 2026 at 09:48 AM_

## Autonomous Run Complete

- Design: posted
- Plan: posted (7 tasks)
- Execute: all tasks done
- Verify: lint pass, 11 unit tests pass
- PR: https://github.com/vig-os/devcontainer/pull/155
- CI: PR Title Check pass

---

# [Comment #4]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Scope resolved: **VS Code only.** Cursor **editor** support is being dropped along with `cursor-agent` as part of #625 (see #629), so the Cursor-URI remote wrapper is no longer wanted. Closing — the VS Code half is tracked under #231 (de-scoped to `code-remote` only).

