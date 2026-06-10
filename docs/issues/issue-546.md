---
type: issue
state: open
created: 2026-05-15T13:52:28Z
updated: 2026-05-15T13:52:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/546
comments: 0
labels: feature, priority:medium, area:workspace, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-16T05:32:49.639Z
---

# [Issue 546]: [[FEATURE] Slim Claude Code OAuth-token forwarding (replace setup-claude.sh + sed-YAML editing)](https://github.com/vig-os/devcontainer/issues/546)

### Description

Replace the current Claude Code injection path (`setup-claude.sh` + `inject_claude_auth` in `devc-remote.sh`) with a slim, robust forwarding mechanism. Depends on #545 (Claude Code baked into image + `IS_SANDBOX=1`).

### Problem Statement

PR #166 ships two pieces for in-container Claude Code:

1. `assets/workspace/.devcontainer/scripts/setup-claude.sh` (~200 lines) — installs Node.js via apt with clock-skew workarounds, `npm install -g @anthropic-ai/claude-code`, creates a non-root `claude` user, ACLs the workspace, wraps `claude` so root invocations `runuser` into that user.
2. `scripts/devc-remote.sh:386-440` `inject_claude_auth` — reads `CLAUDE_CODE_OAUTH_TOKEN` from env or macOS Keychain, then sed-edits `docker-compose.local.yaml` with several heuristic branches (`grep -q 'services: {}'`, `grep -q 'environment:'`, etc.) to inject the env var.

Both have problems:

- **Container-side install is redundant** once Claude Code is baked into the image (#545).
- **The non-root `claude` user + runuser wrapper + ACLs** is ~80 lines of complexity to dodge the uid-0 refusal. `IS_SANDBOX=1` (#545) makes all of this unnecessary.
- **Sed-on-YAML editing is fragile.** Multiple branches based on `grep` patterns; any `docker-compose.local.yaml` the user has customized in unexpected ways will get mangled. No round-trip-safe parser.
- **Mac-side keychain read** (`security find-generic-password -s devc-remote -a CLAUDE_CODE_OAUTH_TOKEN`) duplicates `claude-switch` slot logic. A user managing multiple Anthropic accounts via `claude-switch` has no way to pick which one ships to the container.

### Proposed Solution

A ~50-line replacement that:

1. **Drops `setup-claude.sh` entirely.** Image bake handles install; `IS_SANDBOX=1` env handles uid check; no separate user needed.
2. **Drops sed-on-YAML in `inject_claude_auth`.** Uses one of:
   - `compose exec -e CLAUDE_CODE_OAUTH_TOKEN=$value ...` — per-exec env injection, no compose file edits at all
   - bind-mount of `~/.claude/.credentials.json` (file or via per-user dir) — auth state synced from host, container reads it directly
3. **Sources the token from a defined chain:**
   - `--account <slot>` flag → `~/.claude-creds-mac/<slot>/cred` (claude-switch slot)
   - `~/.claude-creds-mac/.active` → that slot
   - macOS Keychain `Claude Code-credentials/$USER` → live (auto-refreshed) value
   - Linux `~/.claude/.credentials.json`
4. **Warns when the credential's `expiresAt` is in the past** so users know to refresh before deployment fails inside the container with HTTP 401.

### Out of Scope

- The image bake itself (#545)
- Tailscale (#85)
- `devc-remote.sh` broader refactor (separate, larger issue)

### Changelog Category

Changed (replaces existing flow)
