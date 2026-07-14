---
type: issue
state: closed
created: 2026-07-13T12:24:26Z
updated: 2026-07-13T16:17:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1017
comments: 1
labels: chore
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T04:57:28.692Z
---

# [Issue 1017]: [chore(nix): resolve benign nixpkgs eval warnings in the dev-shell](https://github.com/vig-os/devkit/issues/1017)

Found during 1.1.0-rc1 validation (PR #1014).

Entering the dev-shell emits two benign nixpkgs evaluation warnings:
- a `'system'` argument rename/deprecation
- `nixfmt-rfc-style` (renamed upstream)

Purely cosmetic noise; no functional impact. Fix only if it is a clean,
low-risk change to `nix/devtools.nix` / `nix/hooks.nix` / `flake.nix` — the Nix
toolchain is load-bearing and is not worth destabilising to silence two warnings.

Refs: #988
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 04:17 PM_

Fixed by #1018 (commit `1f486439` — `chore(nix): resolve benign nixpkgs eval warnings`), released in [1.1.0](https://github.com/vig-os/devkit/releases/tag/1.1.0).

The devkit's own dev-shell no longer emits the `'system'` rename or `nixfmt-rfc-style` warnings. Note the same `'system'` warning still fired for *scaffolded consumers* via the shared overlay — tracked and fixed separately in #1021 / #1022.

