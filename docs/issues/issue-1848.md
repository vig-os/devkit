---
type: issue
state: open
created: 2026-10-07T12:16:02Z
updated: 2026-10-07T12:16:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1848
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-08T08:45:26.972Z
---

# [Issue 1848]: [Language detection counts *.nix in nested git worktrees (e.g. .claude/worktrees/*), adds nix to DEVKIT_LANGUAGES](https://github.com/vig-os/devkit/issues/1848)

## What happens

`install.sh --force` (1.18.0) language detection counts `*.nix` files in **nested git worktrees** inside the checkout. Agent tooling commonly keeps those under an untracked dir such as `.claude/worktrees/<name>/` (excluded via `.git/info/exclude`). Each worktree has its own `flake.nix`, so the scaffold:

- writes `DEVKIT_LANGUAGES=rust,nix` back to `.vig-os` (the project has only the root `flake.nix`), and
- appends the Nix block to `.gitignore`.

A CI checkout has no such worktrees, so the same scaffold run in CI detects only `rust`. The result is a declaration that differs depending on where the upgrade ran.

## Repro

1. A rust consumer whose only nix file is the root `flake.nix`.
2. `git worktree add .claude/worktrees/x -b x` (and exclude the dir in `.git/info/exclude`).
3. Run `install.sh --force .` on a clean branch: `.vig-os` gets `DEVKIT_LANGUAGES=rust,nix`, and `.gitignore` gets the `# ── Nix ──` block.

## Expected

Detection considers only files git tracks (`git ls-files '*.nix'`), or at least skips nested worktrees (directories containing a `.git` file) and ignored/excluded paths.

