---
type: issue
state: closed
created: 2026-07-14T11:20:45Z
updated: 2026-07-14T12:18:27Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1053
comments: 1
labels: feature, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:27.519Z
---

# [Issue 1053]: [feature(workspace): extend provenance banners to JSONC files (check-json exclude)](https://github.com/vig-os/devkit/issues/1053)

## Problem

Deviation documented in #1036 / PR #1043: the JSONC scaffold files (`.devcontainer/devcontainer.json`, `.vscode/settings.json`, `.devcontainer/workspace.code-workspace.example`) accept `//` comments in their consumers (VS Code, devcontainer CLI) but were skip-listed from the provenance banner because the repo's (and the scaffold's) `check-json` pre-commit hook parses them strictly — a `//` banner fails the suite upstream and downstream.

## Fix

- Exclude the three JSONC paths from the `check-json` hook in `nix/hooks.nix` (the SSoT; both rendered `.pre-commit-config.yaml` files follow, drift-gated by `tests/test_flake_hooks.py`) — or switch them to a JSON5-aware check if one is already available in the hook env.
- Add a `//` comment style to the `Banner` transform and remove the three paths from `_BANNER_SKIP` (`scripts/sync_manifest.py`), so they get the managed/preserved variant like every other comment-capable file.

## Acceptance criteria

- [ ] The three JSONC files carry the correct banner variant
- [ ] `check-json` (both hook configs) stays green; strict-JSON files (`renovate.json` etc.) remain banner-free and strictly checked
- [ ] `sync-manifest` tamper-gate covers the new banners

Refs: #1036
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:18 PM_

Implemented in #1064 (merged to dev): jsonc `//` banner style; the three JSONC files carry the managed banner; check-json excludes exactly those paths (nix/hooks.nix SSoT, both renders); integration tests made JSONC-tolerant.

