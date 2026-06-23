---
type: issue
state: open
created: 2026-03-06T20:44:36Z
updated: 2026-06-23T06:56:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/231
comments: 1
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:55.829Z
---

# [Issue 231]: [[FEATURE] IDE-agnostic remote connection wrappers (cursor-remote, code-remote)](https://github.com/vig-os/devcontainer/issues/231)

## Summary

Create thin IDE-specific wrappers that connect to a devcontainer over Tailscale SSH. These sit on top of `devc-remote.sh` (#152) and the Tailscale key injection (#230) — they only handle the "open IDE via SSH remote" step.

## Context

Currently `devc-remote.sh` does both infra (compose up) and IDE (open Cursor via devcontainer URI). These should be separated:

1. **`devc-remote.sh`** — infra only: SSH to remote, inject Tailscale key, compose up, output Tailscale hostname. No IDE dependency.
2. **IDE wrappers** — take a Tailscale hostname (or receive it from `devc-remote.sh`), open the IDE via SSH remote.

This separation allows:
- Using any IDE (Cursor, VS Code, JetBrains Gateway, plain SSH)
- Scripting without IDE dependency (CI, automation)
- Composing the pieces differently per user preference

## Proposed wrappers

### `cursor-remote.sh`

```bash
#!/bin/bash
# Usage: cursor-remote.sh <tailscale-hostname> [workspace-folder]
cursor --remote "ssh-remote+root@${1}" "${2:-/workspace}"
```

### `code-remote.sh`

```bash
#!/bin/bash
# Usage: code-remote.sh <tailscale-hostname> [workspace-folder]
code --remote "ssh-remote+root@${1}" "${2:-/workspace}"
```

### Integration with `devc-remote.sh`

`devc-remote.sh` should:
1. Output the Tailscale hostname to stdout (or export it)
2. Optionally accept `--open cursor|code|none` to auto-invoke a wrapper
3. Default to `--open none` (infra only) when Tailscale is active, `--open cursor` for legacy devcontainer-protocol mode

## Scope

- Create `scripts/cursor-remote.sh` and `scripts/code-remote.sh`
- Refactor `devc-remote.sh` to separate `open_editor()` from compose lifecycle
- Add `--open` flag to `devc-remote.sh`
- Update docs

## Depends on

- #230 (Tailscale key injection)
- #152 (devc-remote.sh)

## Does NOT include

- JetBrains Gateway support (future, different protocol)
- Neovim/SSH (already works with plain `ssh root@<hostname>`)
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Scope update from the Nix/Claude migration (#625, #629): Cursor **editor** support is being dropped along with `cursor-agent`, so this should be **de-scoped to `code-remote` only** (VS Code `vscode-remote://` URI). The `cursor-remote` half is no longer wanted — #153 has been closed for that reason.

