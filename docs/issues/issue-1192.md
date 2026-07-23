---
type: issue
state: closed
created: 2026-07-17T16:53:17Z
updated: 2026-07-20T16:48:08Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1192
comments: 1
labels: bug, priority:blocking, area:ci, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-21T05:27:43.897Z
---

# [Issue 1192]: [setup-devkit-toolchain direnv path breaks on self-hosted runners with preinstalled Nix](https://github.com/vig-os/devkit/issues/1192)

## Description

1.4.0-rc3 validation on exo-pet/exo-fleet (PR exo-pet/exo-fleet#230 — the first live exercise of the #1173 `DEVKIT_CI_RUNNER` knob) fails on every toolchain job routed to the self-hosted runner:

```
Aborting: Nix is already installed at /nix/var/nix/profiles/default/bin/nix
...
error: syntax error in configuration line 'experimental-features' in "NIX_CONFIG"
```

## Root cause

The direnv branch of `setup-devkit-toolchain` hard-codes `cachix/install-nix-action` (with `extra_nix_config`), assuming a fresh hosted runner. On a self-hosted runner that already ships Nix — the primary use case the #1173 runner knob exists for — the install action aborts, and the `NIX_CONFIG` it leaves behind is malformed, so the very next `nix develop` dies parsing it. The runner routing itself worked exactly as designed (resolve-toolchain/dependency-review stayed hosted, toolchain jobs landed on the self-hosted runner).

## Fix

1. New `Detect host Nix` step (direnv mode) emitting a `has-nix` output.
2. Gate the `install-nix-action` step on `has-nix != 'true'` (fresh runners unchanged).
3. New `Configure host Nix` step for `has-nix == 'true'`: export the same settings (experimental-features, accept-flake-config, vig-os substituter+key) via a well-formed multi-line `NIX_CONFIG` heredoc to `GITHUB_ENV`. (On a multi-user host Nix the substituter entries may be ignored for non-trusted users — acceptable, Cachix is an optimization.)

TDD: executed-bash test of the new config step (assert GITHUB_ENV carries a well-formed newline-separated NIX_CONFIG) + structural assertions on the step conditions.

Targets `release/1.4.0` per the RC-validation runbook (third rc finding after #1187, #1189); rc4 follows. Blocks only the direnv+self-hosted combination — the four hosted-runner validation lanes are green on rc3 and unaffected by this path.

## Impact

Blocks 1.4.0 for self-hosted direnv consumers (exo-fleet).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 20, 2026 at 04:48 PM_

Fixed via PR #1193 (merged into release/1.4.0 @37ef2fa5, rc4): "Detect host Nix" step gates install-nix-action on has-nix, and "Configure host Nix" writes a well-formed NIX_CONFIG. Live-proven end-to-end on exo-pet/exo-fleet#230 (meatgrinder) at rc4, and re-proven on rc5/rc6/final — "Configured preinstalled host Nix via NIX_CONFIG." in every toolchain job. Shipped in 1.4.0. Follow-up refinement of the detect probe (ambient NIX_CONFIG scrub) was #1216, also fixed and shipped in 1.4.0 via PR #1217.

