---
type: issue
state: open
created: 2026-10-16T23:14:38Z
updated: 2026-10-16T23:14:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1900
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-17T06:49:13.300Z
---

# [Issue 1900]: [[BUG] ci.yml Commit Messages lane: `uv run <vig-utils tool>` syncs the consumer's project venv from PyPI](https://github.com/vig-os/devkit/issues/1900)

## Problem
In the managed `ci.yml` (devkit 1.18.0), the Commit Messages job runs the vig-utils tools through `uv run`:
- `uv run validate-branch-name …`
- `uv run validate-commit-range …`
- `uv run check-pr-agent-fingerprints`

In direnv mode these tools are already on `PATH` from the Nix toolchain that `setup-devkit-toolchain` provisions. In a consumer repo with a `pyproject.toml`, though, `uv run` first syncs the project environment: it resolves and installs every project dependency from PyPI into a fresh `.venv` before it runs the tool. On ephemeral runners that means a full download and install on every run, just to run a tool that is already installed. It also breaks consumers whose project environment is not managed by uv. For example, MorePET/anatomist is moving to a uv2nix environment where uv only writes `uv.lock` and never installs anything (its ADR-0004, MorePET/anatomist#104).

## Proposal
In direnv mode, run the tools without touching the project environment. Either:
- call them straight from the Nix store (they are on `PATH` after setup-devkit-toolchain), or
- use `uv run --no-sync`.

Devcontainer and bare modes can keep today's behaviour if they need it.

## Acceptance
- The Commit Messages job creates no `.venv` and downloads no project dependency in a direnv-mode consumer.
- The tools still resolve to the same versions as today (the toolchain's vig-utils).
