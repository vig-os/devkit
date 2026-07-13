---
type: issue
state: open
created: 2026-07-13T12:24:26Z
updated: 2026-07-13T12:24:26Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1017
comments: 0
labels: chore
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:51.018Z
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
