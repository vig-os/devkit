---
type: issue
state: closed
created: 2026-07-17T09:57:21Z
updated: 2026-07-17T11:35:55Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1172
comments: 1
labels: feature, priority:medium, area:workspace, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:26.480Z
---

# [Issue 1172]: [gitleaks as an opt-in base hook (secret scanning beyond detect-private-key)](https://github.com/vig-os/devkit/issues/1172)

### Description

Add `gitleaks` to the shared toolchain and define it as an **opt-in** (default-disabled) hook on the consumer flake hook surface, resolved from the flake as `language: system`.

### Problem Statement

Devkit's only secret-adjacent hook is `detect-private-key`. Secret-bearing consumers in the deployment queue (`exo-pet/exo-fleet` and `Personal/vigo-nixos`, both with sops-managed secret files and tuned `.gitleaks.toml` allowlists) run gitleaks today via the upstream pre-commit repo hook — which does a slow git-clone/build and breaks offline. exo-fleet's CI and developers permanently `SKIP=gitleaks` the repo hook and run a nix-pinned binary separately: exactly the failure mode devkit's `language: system` hooks were built to eliminate.

### Proposed Solution

- Add `gitleaks` to `nix/devtools.nix` (dev-shell + image + `vigos.packages`).
- Define a `gitleaks` hookDef in `nix/hooks.nix`: `language: system`, **`scaffold = false` and default-disabled on the consumer generation surface** — consumers enable via `mkProjectShell { hooks = { gitleaks.enable = true; }; }`. Use the pre-commit invocation appropriate to the nixpkgs-pinned gitleaks version (`gitleaks git --pre-commit --staged --redact` on v8.19+). A repo-root `.gitleaks.toml` is picked up automatically by gitleaks; no extra plumbing.
- Document the opt-in (and `.gitleaks.toml`) in `docs/NIX.md` hook-customization section.

### Alternatives Considered

- Enabled-by-default: rejected for now — false-positive tuning is repo-specific and a red first `just precommit` on every existing consumer is a bad upgrade experience.
- trufflehog/detect-secrets: gitleaks is what the target consumers already run and tune.

### Additional Context

Recon from the exo-fleet deployment assessment (2026-07-17): `SKIP=nixpkgs-fmt,shellcheck,gitleaks` is the daily driver there. Related: #1171 (nix consumer support), sops-nix secret surfaces.

### Impact

- Opt-in only: zero behavior change for consumers that don't enable it. Backward compatible (semver:minor).

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 11:35 AM_

Shipped via PR #1175, merged to `dev` (dev-PR `Closes` does not auto-close — closing manually). Reaches consumers with the next devkit release.

