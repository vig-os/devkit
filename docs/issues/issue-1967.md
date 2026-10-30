---
type: issue
state: open
created: 2026-10-29T12:04:58Z
updated: 2026-10-29T12:04:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1967
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:26.125Z
---

# [Issue 1967]: [devShells ship claude-code by default and shadow the machine's own claude wrapper](https://github.com/vig-os/devkit/issues/1967)

## Problem
devkit adds `claude-code` to every project's devShell (flake.nix around line 111, under the fast-mover overlay: "claude (claude-code) is an agent CLI that moves very fast; track unstable"). With direnv's `use flake`, the devShell is prepended to `PATH`, so inside any devkit-scaffolded repo `claude` resolves to devkit's unwrapped claude-code store path instead of the machine's own `claude`.

On managed machines the system `claude` is often a wrapper, not the bare binary. It selects a pinned release channel and loads per-profile credentials before it execs Claude Code. The devShell copy bypasses all of that. As a result:
- **The version depends on each repo's devkit lock**, not on the machine's chosen channel.
- **Per-profile credential loading is skipped.** A profile that relies on a provisioned token, with no interactive login, opens the login wizard.
- **The same agent behaves differently** depending on whether direnv loaded in its shell.

## Proposal
Treat the agent CLI as a machine-level tool, not a project build input:
1. Do **not** include `claude-code` in project devShells by default.
2. Offer it as an **explicit opt-in** (e.g. a `withAgentCli = true` flag) for machines that have no `claude` of their own, and document that opting in shadows any system wrapper.
3. Note it in the upgrade or changelog notes, because repos that relied on the devShell copy need a system install or the opt-in.

## Acceptance
- A freshly scaffolded project's devShell has no `claude` on PATH unless it opts in.
- With the opt-in, `claude` is present as today.
- A test or flake check asserts the default devShell's PATH contains no claude-code.

## Repro
In any devkit project with `use flake` loaded: `command -v claude` prints `/nix/store/…-claude-code-<ver>/bin/claude`. Outside the project it prints the machine's own `claude`.
