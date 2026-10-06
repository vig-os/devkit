---
type: issue
state: open
created: 2026-10-05T18:35:55Z
updated: 2026-10-05T18:35:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1826
comments: 0
labels: bug, priority:medium, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: 1833
children: none
synced: 2026-10-06T08:51:00.585Z
---

# [Issue 1826]: [Upgrade preflight: untracked build output blocks the upgrade that would add its .gitignore fragment](https://github.com/vig-os/devkit/issues/1826)

## Problem
The upgrade preflight refuses on any untracked file. In a repo that adds a language after the first scaffold, the build output blocks the very upgrade that would add its ignore rules.

## Repro
1. Scaffold a language-neutral repo.
2. Add `Cargo.toml` and run `cargo build`, which creates `target/`.
3. Run `install.sh --force` to pick up the Rust `.gitignore` fragment and `DEVKIT_LANGUAGES=rust`.
4. Result: `error: preflight: refusing to upgrade on a dirty tree.`

`target/` is untracked only because the fragment that ignores it arrives with that same upgrade. The same applies to `node_modules/`, `.venv/` and Nix `result` links. The current workaround is to move the build directory aside for the run.

## Proposed
- Exclude paths the upgrade's own `.gitignore` fragments are about to ignore from the dirtiness check.
- Name the offending paths in the error message, and offer `--allow-untracked`.

