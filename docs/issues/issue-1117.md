---
type: issue
state: closed
created: 2026-07-15T12:31:23Z
updated: 2026-07-15T14:24:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1117
comments: 1
labels: bug, priority:medium, area:workspace, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:01.886Z
---

# [Issue 1117]: [#1092 pre-commit-ignore auto-seed misses direnv-mode (containerized) upgrades; scaffold clobbers the flake-hooks symlink](https://github.com/vig-os/devkit/issues/1117)

## Summary

The #1092 fix seeds the `.pre-commit-config.yaml` ignore automatically, "gated
strictly on the store-symlink condition." In **direnv mode**, `install.sh` runs
`init-workspace` inside the devcontainer image, where `/nix/store` is not
mounted, so the flake-generated `.pre-commit-config.yaml` symlink is **dangling**
from the container's point of view. The store-symlink condition is not detected,
so on a flake-hooks (`hooks = { }`) consumer:

1. the ignore is **not** seeded into the managed `.gitignore`, and
2. the scaffold writes a real template `.pre-commit-config.yaml` **over** the
   (dangling) symlink.

Net result: a committed template file that is not ignored and shadows the
flake-generated config, until reconciled by hand.

## Impact

Every direnv-mode flake-hooks consumer. The 1.2.1 fix effectively only covers
the non-container (devcontainer) path where the symlink resolves.

## Reproduction

Consumer `vig-os/commit-action` (direnv, `hooks = { }` in `flake.nix`),
1.2.0 → 1.2.1. Before: `.pre-commit-config.yaml` →
`/nix/store/…-pre-commit-config.json` (symlink, gitignored). After
`install.sh --force --version 1.2.1 .`:

- `.pre-commit-config.yaml` is a real ~6 KB template file (not the symlink)
- `git check-ignore -v .pre-commit-config.yaml` → not ignored (the prior ignore
  line was dropped from the regenerated managed `.gitignore` and not re-seeded)

## Expected

Detect the store-symlink condition by the link **target** (`readlink`, i.e. the
path points into the flake store) rather than by resolving it, so it holds even
when `/nix/store` is absent in the container. When it holds: seed the ignore and
do **not** overwrite the symlink with a template.

## Workaround (downstream)

Deleted the template, moved the `.pre-commit-config.yaml` ignore into the new
consumer-owned `.gitignore.project` (#1092), and regenerated the symlink via
`nix develop`. See PR `vig-os/commit-action#80`. Follow-up to #1092.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:24 PM_

Fixed by #1124 (merged into `dev`). All presence gates now treat a symlink of any kind — including a dangling host-store symlink in direnv-in-container mode — as present via `path_present()`: the flake-hooks symlink survives the template rsync, the #1092 ignore auto-seed fires, `--preview` classifies it PRESERVED, and the #878 divergence guard sees the pre-existing config. Ships with the next patch release.

