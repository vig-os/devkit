---
type: issue
state: open
created: 2026-07-13T13:51:40Z
updated: 2026-07-13T13:53:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1021
comments: 0
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: c-vigo
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:50.152Z
---

# [Issue 1021]: [[BUG] Consumer overlay reads deprecated final.system → 'system' renamed warning in consumer nix develop](https://github.com/vig-os/devkit/issues/1021)

### Description

Follow-up to #1017. The nixpkgs `'system' has been renamed to/replaced by
'stdenv.hostPlatform.system'` eval warning is resolved for the devkit's **own**
dev-shell but still fires for a **scaffolded consumer's** `nix develop`.

Root cause is a deprecated attribute read in the **shared consumer overlay**
(`vigos.overlays.default`):

```nix
# flake.nix:114-119
# System-independent overlay for downstream consumers (overlays.default).
overlay =
  final: prev:
  (mkFastMoverOverlay (importUnstable final.system) final prev) // (vigUtilsOverlay final prev);
#                                   ^^^^^^^^^^^^^ deprecated
```

`final.system` is the renamed-away attribute. When a consumer applies
`overlays.default` and `mkProjectShell` forces a fast-mover package, `final.system`
is evaluated → warning.

Why it slipped past #1017: the devkit's **own** dev-shell uses a different code
path (the hoisted `importUnstable` with a concrete system, per the comment at
flake.nix:116), so it evaluates clean; only the consumer-facing `overlays.default`
path reads `final.system`. Validation against the devkit itself therefore looked
fully fixed while the consumer residual survived (seen in the 1.1.0-rc2 validation,
PR #1014).

### Reproduction

Scaffold a direnv workspace from `ghcr.io/vig-os/devcontainer:1.1.0-rc2`, pin the
flake to the RC, and `nix develop`:

```
evaluation warning: 'system' has been renamed to/replaced by 'stdenv.hostPlatform.system'
```

The devkit's own `nix eval .#devShells.x86_64-linux.default.drvPath` is clean.

### Fix

`flake.nix:119`: `importUnstable final.system` → `importUnstable final.stdenv.hostPlatform.system`.

The codebase already uses the correct idiom at `flake.nix:314`
(`pkgs.stdenv.hostPlatform.system`).

### Acceptance Criteria

- [ ] A scaffolded consumer's `nix develop` emits no `'system' has been renamed` warning.
- [ ] Devkit's own dev-shell remains clean.

### Notes

Cosmetic (a warning, not an error); **not** a 1.1.0 promotion blocker. Suitable
for 1.1.x. Not a consumer-side fix — consumers only consume `overlays.default`.

