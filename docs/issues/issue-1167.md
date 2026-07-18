---
type: issue
state: closed
created: 2026-07-17T08:26:20Z
updated: 2026-07-17T09:15:20Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1167
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:27.289Z
---

# [Issue 1167]: [direnv-mode scaffold ships hand-managed pre-commit config whose pymarkdown hook cannot run on host runners](https://github.com/vig-os/devkit/issues/1167)

## Observed

On the greenfield direnv-mode deployment to `vig-os/org-config` (vig-os/org-config#3), the scaffolded hand-managed `.pre-commit-config.yaml` includes `pymarkdown`, whose `pyjson5` native dependency fails with `ImportError: libstdc++.so.6` on the host-runner CI lane that direnv mode resolves to. It only works in container mode (or locally inside the flake dev shell).

## Workaround applied (reference-aligned)

Opted into the flake-generated hook set (`hooks = { }` in `flake.nix`), removed the tracked `.pre-commit-config.yaml` (now a gitignored nix-store symlink) — the same pattern both existing direnv consumers (commit-action, sync-issues-action) converged on, where pymarkdown is dropped since it is not in nixpkgs.

## Proposal

When `DEVKIT_MODE=direnv` (or `bare`), the installer/init-workspace should default to the flake-generated hooks instead of seeding the hand-managed YAML that is only viable in container mode — every direnv consumer has had to make this same manual switch.

Found during the 1.3.1 rollout verification.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 09:15 AM_

Fixed on `dev` via #1168 — a fresh `direnv` scaffold now defaults to flake-generated pre-commit hooks (activates `hooks = { }`, drops the hand-managed `.pre-commit-config.yaml`), so the host-runner CI lane no longer trips on pymarkdown's native `pyjson5`. `bare` is out of scope by design (no flake; consumer owns its toolchain). Ships to consumers on the next devkit release.

