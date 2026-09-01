---
type: issue
state: closed
created: 2026-09-01T07:54:14Z
updated: 2026-09-01T14:11:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1589
comments: 1
labels: feature, area:ci, effort:small, semver:minor
assignees: none
milestone: 1.13.0
projects: none
parent: none
children: none
synced: 2026-09-01T15:12:53.371Z
---

# [Issue 1589]: [[FEATURE] CI: evaluate homeManagerModules against home-manager master + nixos-unstable](https://github.com/vig-os/devkit/issues/1589)

## Description

Add an eval-only CI leg that exercises the exported `homeManagerModules` against **home-manager `master` + `nixos-unstable`**, alongside the existing stable coverage.

## Problem Statement

The `vigos.*` home modules are exported as plain module paths and evaluated against whatever nixpkgs and home-manager the *consumer* supplies — devkit's own `release-26.05` lock governs only its own `homeConfigurations` and checks. That contract is the right one, but it means devkit currently tests only one side of it.

There is now a production consumer on the other side: exo-pet/exo-fleet wires the full module set (`packages`, `shell` incl. `secretsEnv`, `multiplexer`, `sesh`, `cli`, `direnv`, `git`, `claude`) into a NixOS-module server tier (`home-manager.users.<name>`, the first-class platform row in ADR-home-environment-modules) on a flake tracking `nixos-unstable` with home-manager pinned to `master` (exo-pet/exo-fleet#438). The combination was verified clean by building on 2026-09-01 — but nothing guards it going forward. An HM option rename on `master`, or an unstable nixpkgs change under a module default, will surface as a consumer eval break discovered downstream, after a lock bump, in a repo that can't fix it.

## Proposed Solution

A CI job (or `nix flake check` leg) that evaluates a minimal configuration importing **all** `vigos.*` home modules with every `enable` set, against `home-manager/master` + `nixpkgs-unstable` — devkit already carries a `nixpkgs-unstable` input, so no new inputs are needed. Either a standalone `homeConfiguration` build (activation package, no runtime) or a throwaway `nixosSystem` using the NixOS-module tier, whichever is cheaper; the NixOS-module form matches how the server consumer actually wires it.

Blocking, not allowed-to-fail: an eval break on master+unstable is a real consumer break, and the fix (a version-guarded option or a compat note) is exactly what the leg exists to force before release.

## Alternatives Considered

- **Status quo (stable-only testing)** — leaves the exported-paths contract untested on the branch combination a production consumer runs.
- **Consumer-side CI only** — exo-fleet's own dev-vm build leg does catch breaks, but after the fact and per-consumer; the module set is devkit's surface and belongs under devkit's release gate.
- **Pinning consumers to stable** — rejected in the consumer's own review: HM release branches against a non-matching nixpkgs *is* the skew, and splitting a fleet across nixpkgs branches costs more than the drift.

## Impact

- Protects every unstable consumer of `homeManagerModules`; the concrete-consumer ask-gate is satisfied by exo-pet/exo-fleet#438 (merged, in production use).
- Small: one eval-only matrix leg, no image or runtime work.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 1, 2026 at 08:49 AM_

Solved by #1590, merged to dev. The eval guard (nixosConfigurations.ci-hm-unstable + blocking Tier-0 test) is live; the weekly fast-branch cron now bumps home-manager-unstable alongside nixpkgs-unstable.

