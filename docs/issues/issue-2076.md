---
type: issue
state: open
created: 2026-11-17T16:11:40Z
updated: 2026-11-17T16:11:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2076
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:46.256Z
---

# [Issue 2076]: [Home and NixOS modules still pin claude-code; make the agent CLI opt-in (default off)](https://github.com/vig-os/devkit/issues/2076)

## Problem
#1967 made the agent CLI an opt-in for project dev shells, but devkit still installs and pins `claude-code` unconditionally on the machine-level surfaces:

- `vigos.packages.enable` (home-manager) adds `agentTools` (claude-code from the fast-mover overlay) to `home.packages`.
- `programs.vigos-devtools.enable` (NixOS module) adds it to `environment.systemPackages`.
- `vigos.claude.enable` exports `DISABLE_AUTOUPDATER=1` session-wide, which turns off the native updater even when devkit does not install claude.

Machines that run their own `claude` (a wrapper that selects a release channel and loads per-profile credentials, or a native install) end up with devkit's pinned copy on PATH next to or ahead of it, and their native updater disabled.

## Proposal
- New options `vigos.packages.agentCli.enable` and `programs.vigos-devtools.agentCli.enable`, **default false**. When enabled, devkit's claude-code is installed as today.
- `DISABLE_AUTOUPDATER` moves to `vigos.packages` and is set only when devkit installs the CLI (Nix then owns updates).
- The container image keeps claude (no host CLI to fall back to); dev shells stay opt-in via `withAgentCli`.

## Acceptance
- With `vigos.packages.enable = true` alone, `home.packages` has no claude-code and `DISABLE_AUTOUPDATER` is unset.
- `vigos.packages.agentCli.enable = true` restores the CLI and the updater variable.
- Same for the NixOS module.
- `tests/agent-cli-policy.nix` asserts both directions.
- Ships in 1.19.1.

