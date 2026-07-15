---
type: issue
state: closed
created: 2026-07-15T08:43:13Z
updated: 2026-07-15T14:37:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1107
comments: 1
labels: refactor, priority:medium, area:image, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 1103
children: none
synced: 2026-07-15T20:04:04.497Z
---

# [Issue 1107]: [Evict the redundant CPython 3.13 interpreter: gitMinimal + actionlint without pyflakes (~127 MiB)](https://github.com/vig-os/devkit/issues/1107)

### Description

The image carries **two** CPython interpreters: `python3-3.14` (the chosen one —
`UV_PYTHON`, `vig-utils`, the toolchain) and a redundant **`python3-3.13.13` at
127 MiB** that nothing in the *chosen* toolchain uses. It is held by **four
independent anchors** (traced with `nix why-depends` / the reference graph):

| Anchor | Path in | Removed by |
|--------|---------|-----------|
| `criu` | podman → crun → criu | the podman-DooD sub-issue |
| `bandit` | ddt/stevedore/gitpython/rich/pygments | the bandit sub-issue |
| full `git-2.54.0` | git-p4 / python helpers | `gitMinimal` (**this issue**) |
| `actionlint` | wraps optional `pyflakes` | drop the wrap (**this issue**) |

**All four must fall** — removing any single anchor leaves the interpreter held
by the rest. This issue owns the git + actionlint anchors and the final
verification; it **depends on** the podman and bandit sub-issues.

Marginal saving once all anchors fall: **~127 MiB** (the interpreter), plus
full-git's own extras (git-doc 15 MiB, gettext 24 MiB, …).

### Proposed mechanism

- **git → `gitMinimal`** in `imageTools`
  (`perlSupport = false; pythonSupport = false; guiSupport = false;
  withManual = false`). Already proven in-closure — bandit's gitpython pulls
  `git-minimal` today.
- **actionlint** → override/wrap without the optional `pyflakes` runtime dep
  (pyflakes only lints inline python in workflow `run:` steps — niche here;
  alternatively realign pyflakes to 3.14 if dropping proves awkward).
- Land **after** the podman and bandit sub-issues, then verify eviction.

### Risk / contract

`gitMinimal` drops `git send-email`, `git svn`, `git p4`, `gitk`, `git gui`,
and built-in man pages (`git help <cmd>`). In a `gh`-driven GitHub-PR workflow
these are unused; `add -p` / `rebase -i` / worktrees are builtin C and stay.
Per the epic's contract note → **`semver:minor`**, epic is the declaration of
record.

Also loses actionlint's inline-python lint on workflow `run:` steps.

### Not solved here

perl 5.42 is **half**-solved here: `gitMinimal` removes one of its two anchors;
the other (`neovim → wl-clipboard → xdg-utils`) is the perl-eviction
sub-issue, which depends on this one.

### Verification

- `nix path-info -r .#devkitImageEnv | grep python3-3.13` returns **nothing**.
- `nix path-info -Sh .#devkitImageEnv` drops ~127 MiB beyond the podman/bandit
  cuts.
- Built image: `git log`/`commit`/`rebase -i`/worktree work; commit signing
  (SSH) works; `actionlint` lints a sample workflow.
- Hooks and `nix flake check` pass.

### Notes

Part of the image-slimming epic. **Depends on** the podman-DooD and bandit
sub-issues (two of the four anchors).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

Implemented and merged to dev in #1126 (−148.8 MiB measured; python3.13 grep empty).

