---
type: issue
state: open
created: 2026-11-03T09:28:07Z
updated: 2026-11-03T09:28:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1996
comments: 0
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:24:01.871Z
---

# [Issue 1996]: [[FEATURE] Local trunk guard: wire guardrails protect-trunk into the scaffold (pre-commit + .githooks/pre-push), workflow-aware](https://github.com/vig-os/devkit/issues/1996)

## Description

Wire the guardrails `protect-trunk` gates into the scaffold as an opt-in, workflow-model-aware **local** trunk guard: a pre-commit hook entry plus a `.githooks/pre-push` entry point. This is the local half of the Free-plan protection story; #1892 is the server-side half.

## Problem Statement

Found while bootstrapping `exoma-ch/ravmatic` (devkit 1.18.0, `--mode direnv --workflow gitflow`, private repo in a Free org). Each step below was verified in that session.

1. **The `guardrails` module ships the gates but nothing runs them.** `modules = [ "guardrails" ]` puts `guardrails-protect-trunk` and `guardrails-protect-trunk-push` on PATH. `nix/modules/guardrails.nix` says hook entries are "rendered by the installer from `DEVKIT_MODULES`", but `init-workspace.sh` 1.18.0 only persists `DEVKIT_MODULES`. It renders nothing from it. Each consumer has to write the hook entry by hand.
2. **The gate defaults miss gitflow's `dev`.** `GUARDRAILS_PROTECTED_BRANCHES` defaults to `main:master`. In a gitflow repo, `dev` is the branch that takes the accidental commits.
3. **`.githooks/` has no `pre-push` entry point.** The scaffold ships `pre-commit`, `commit-msg` and `prepare-commit-msg` only, and `core.hooksPath=.githooks`. So `protect-trunk-push` can't be wired as a `stages = [ "pre-push" ]` flake hook. The consumer adds `.githooks/pre-push` by hand. It survives `--force` (no `--delete`), but devkit doesn't know about it.
4. The existing branch-name validator allows commits on `main` and `dev`. So the stock hook set doesn't stop "right change, wrong branch".

## Proposed Solution

A knob, e.g. `DEVKIT_TRUNK_GUARD=true` (off by default):

- The flake template adds a `protect-trunk` hook entry (`pass_filenames = false`, `always_run = true`). Its branch list comes from the workflow model: `main:dev` for gitflow, `main` for trunk.
- The scaffold ships a managed `.githooks/pre-push` that runs the same dev-shell guard as `pre-commit`, then `exec guardrails-protect-trunk-push` with the same branch list. Stdin is passed straight through, so a multi-ref push such as `git push origin HEAD:main` is checked in full (prek nulls stdin for system hooks).
- `GUARDRAILS_ALLOW_TRUNK=1` stays the documented escape hatch. CI and release bots are already auto-allowed (`CI` / `GITHUB_ACTIONS`).

## Reference implementation

`exoma-ch/ravmatic` (private): `flake.nix` (the `protect-trunk` hook entry and `modules = [ "guardrails" ]`) and `.githooks/pre-push`. Verified there:

- a commit on `main` is refused;
- `git push origin main` is refused;
- `GUARDRAILS_ALLOW_TRUNK=1` passes;
- the pre-push file survives `install.sh --force`, and scaffold drift stays green.

## Related

- #1892: the server-side tripwire. The two halves together are "fake" branch protection for Free-plan private repos.
- #1488 / #1400: the guardrails module.
- #1829: hooks inactive before the first shell entry.

