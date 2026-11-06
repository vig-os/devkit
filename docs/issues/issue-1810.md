---
type: issue
state: open
created: 2026-10-04T14:47:45Z
updated: 2026-10-04T14:47:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1810
comments: 0
labels: bug, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-05T08:48:21.950Z
---

# [Issue 1810]: [mkRustProject drops the .vig-os hook knobs, so the Rust scaffold fails deadnix/statix](https://github.com/vig-os/devkit/issues/1810)

## Description

A repo scaffolded with the Rust language pack (`vigos.lib.mkRustProject`, devkit 1.17.0) gets a
`flake.nix` that **fails its own pre-commit hooks**, and whose `.vig-os` knobs are silently ignored.
Both come from the same gap: `mkRustProject` has no `branchTypes` / `commitTypes` / `refsPolicy` /
`refsOptionalTypes` arguments.

Seen in `vig-os/stepv`.

## Problem 1: the knobs don't reach the hooks

The scaffolded flake computes `branchTypes`, `commitTypes`, `refsPolicy` and `refsOptionalTypes`
from `.vig-os` (the managed block marked "leave it"), but has nowhere to pass them: `mkRustProject`
doesn't accept them, unlike `mkProjectShell`. Setting `DEVKIT_BRANCH_TYPES` (etc.) in a Rust repo
is therefore **silently ignored** by the flake-generated branch guard and commit-message hook.

## Problem 2: the scaffold fails deadnix and statix

Because those bindings are computed and never used, a fresh Rust scaffold fails:

- **deadnix:** `Unused let binding: vigOsList / branchTypes / commitTypes / refsPolicy /
  refsOptionalTypes`
- **statix [04]:** `checks = rust.checks; packages = rust.packages;` should be
  `inherit (rust) checks packages;`

The first commit touching `flake.nix` then can't pass the hooks without `--no-verify` or hand edits
to the managed block. stepv works around it with `# deadnix: skip` on the five bindings and the
`inherit`.

## Proposed solution

Add the four arguments to `mkRustProject` and forward them as `mkProjectShell` does, and have the
Rust scaffold pass them, which fixes both problems. Emit `inherit (rust) checks packages;` in the
template.

## Repro

Scaffold a repo with `DEVKIT_LANGUAGES=rust` on 1.17.0, then run `prek run --files flake.nix`.

