---
type: issue
state: closed
created: 2026-07-22T16:51:42Z
updated: 2026-07-23T16:00:13Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1255
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-24T05:27:30.358Z
---

# [Issue 1255]: [Upgrade deploys template .pre-commit-config.yaml into direnv consumers, shadowing the flake-generated config](https://github.com/vig-os/devkit/issues/1255)

## Description

An `install.sh --force` upgrade on a `direnv`-mode consumer deploys the scaffold template `.pre-commit-config.yaml` whenever the file is absent from the tree — but in direnv mode that file is flake-GENERATED (#1167), gitignored, and intentionally absent in a fresh checkout/worktree. The deployed template then SHADOWS the generated config: git-hooks.nix generation refuses to overwrite an existing file, so the consumer's shell silently runs the generic template without the consumer's `hooksExcludes`/`hooks` customizations (e.g. commit-action's `^dist/` exclude — typos then flags the committed ncc bundle).

Fresh direnv scaffolds already drop the YAML correctly; only the upgrade path deploys it.

Observed during the 1.4.1-rc2 consumer lane bumps (fresh worktree from `origin/dev` of commit-action, upgrade to rc2 → template YAML appears as a regular file; the repo's real checkout has the store symlink). A/B with the 1.4.0 installer reproduces identically — pre-existing, NOT a 1.4.1 regression.

## Expected Behavior

The upgrade path applies the same direnv-mode drop-hooks handling as a fresh scaffold: never deploy `.pre-commit-config.yaml` into a mode whose config is flake-generated (and never overwrite/shadow a generated one).

## Impact

Gitignored, so CI and PRs are unaffected; local dev shells lose flake excludes silently until the file is deleted (regeneration resumes on next shell entry).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 04:00 PM_

Fixed by PR #1259 (flake-hooks opt-in detected from the preserved `flake.nix`; template YAML excluded from copy + preview, #1092 ignore seed kept firing), merged into `release/1.4.1`. Live-proven at rc4: a fresh commit-action worktree upgrade printed the #1255 skip notice, deployed no YAML, and kept the gitignore entry. Shipped in [1.4.1](https://github.com/vig-os/devkit/releases/tag/1.4.1).

