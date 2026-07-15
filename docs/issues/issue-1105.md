---
type: issue
state: closed
created: 2026-07-15T08:43:09Z
updated: 2026-07-15T14:37:11Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1105
comments: 1
labels: refactor, priority:medium, area:image, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 1103
children: none
synced: 2026-07-15T20:04:05.283Z
---

# [Issue 1105]: [Drop vestigial baked bandit from imageTools (stray CPython 3.13 stack, ~74 MiB)](https://github.com/vig-os/devkit/issues/1105)

### Description

`bandit` sits in `imageTools`, but nixpkgs builds it against **CPython 3.13**
while the entire rest of the image is **3.14** (`UV_PYTHON`, `vig-utils`, the
toolchain). That one entry drags a partial second Python stack into the
closure: `bandit` → ddt/stevedore/pyyaml/rich (→ markdown-it-py → mdurl,
pygments) / gitpython (→ gitdb → smmap), and — via gitpython — a full
**`git-minimal` (52 MiB)**, even though the image already ships full `git`.

Marginal saving (measured on `.#devkitImageEnv`): **~74 MiB** across 13 paths.
`nix why-depends` confirms nothing else in the image needs any of them.

**The baked copy is already vestigial.** The committed
`.pre-commit-config.yaml:198` runs `entry: uv run bandit …` — the *venv*
bandit, pinned in `pyproject.toml` (`lint`/`devkit` extras,
`bandit[toml]==1.9.4`). The only Nix-bandit consumer is
`nix/hooks.nix:512` (`${pkgs.bandit}/bin/bandit`) in the sandbox-pure
`checks.pre-commit` profile — which is **outside the image closure** and stays
untouched.

> Note: this frees the 3.13 *packages* + `git-minimal`. It does **not** by
> itself free the 127 MiB `python3-3.13` *interpreter*, which has three other
> anchors — see the interpreter-eviction sub-issue. This cut removes **one** of
> its four anchors.

### Proposed mechanism

Remove `bandit` from `imageTools` (`flake.nix`). Image-mode users get it via
`uv run bandit` / `uvx bandit`, exactly as the committed hooks already do.

(Alternative considered: realign to `python314Packages.bandit`. Rejected —
keeps a redundant tool baked, pays an uncached 3.14 rebuild, and the hook path
doesn't use it anyway.)

### Verification

- `nix path-info -Sh .#devkitImageEnv` drops ~74 MiB; `git-minimal` and all
  `python3.13-*` package paths gone from the closure.
- `pre-commit run bandit --all-files` (via `uv run`) still passes in the image.
- `nix flake check` (`checks.pre-commit`) unaffected.

### Notes

Part of the image-slimming epic. Independent; one of the four anchors gating
interpreter eviction.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

Implemented and merged to dev in #1120 (−74.5 MiB measured).

