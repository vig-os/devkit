---
type: issue
state: closed
created: 2026-07-17T09:56:40Z
updated: 2026-07-17T11:35:51Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1170
comments: 1
labels: feature, priority:high, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:27.018Z
---

# [Issue 1170]: [Package pymarkdown in the flake and promote it to a system hook (direnv consumers lose markdown lint)](https://github.com/vig-os/devkit/issues/1170)

### Description

Package `pymarkdownlnt` as a Nix derivation inside the devkit flake and promote the `pymarkdown` hook from a runner-only remote-repo hook to a full `language: system` hook, resolved from the shared toolchain like shellcheck/typos/yamllint.

### Problem Statement

`pymarkdown` is the one documented residual of the single-SSoT hook system (`nix/hooks.nix:402`, `docs/NIX.md`): it is not in nixpkgs, so neither the sandbox gate nor the consumer flake-hook generation can resolve it. #1167/#1168 made **direnv** scaffolds default to flake-generated hooks (the hand-managed YAML's pymarkdown hook cannot run on bare host runners — native `pyjson5` fails with `ImportError: libstdc++.so.6`), which means **every direnv consumer silently loses markdown linting entirely**.

This is now blocking: the next deployment wave (exo-pet/vault, exo-pet/exo-fleet, later Personal/vigo-nixos) is direnv-only, and vault is a *documentation vault* — 90+ markdown files with a load-bearing `.pymarkdown` config. Shipping it with no markdown lint is not acceptable.

### Proposed Solution

- Package `pymarkdownlnt` via `buildPythonPackage` (PyPI). Feasibility verified: the problematic native dep `pyjson5` **is in nixpkgs** (2.0.1); the remaining deps (`application_properties`, `columnar`) are small pure-Python packages that need packaging too. Pin to the version currently pinned in the hand-managed YAML lineage (v0.9.23) or newer.
- Add it to `nix/devtools.nix` so it reaches all three delivery surfaces (dev-shell, image, `vigos.packages`).
- In `nix/hooks.nix`, convert the `pymarkdown` hookDef to `language: system` (entry on PATH) for all three artifacts: committed runner YAML, sandbox `checks.pre-commit` gate, and the consumer generation surface — same args/config resolution (`-c .pymarkdown fix`) and excludes as today.
- Retire the "drops pymarkdown" residual: update the `activate_flake_hooks_default()` scaffold messaging in `assets/init-workspace.sh` (#1168), the residual notes in `docs/NIX.md`, and the hookDef comment.

### Alternatives Considered

- **Switch to nixpkgs' markdownlint-cli2/mdformat**: rejected — rule-config churn across every consumer and abandons the tuned `.pymarkdown` SSoT (`.pymarkdown` + `.pymarkdown.config.md` are preserved scaffold templates, #1099).
- **`uvx pymarkdownlnt` wrapper hook**: rejected — network-dependent first run, impure, against the offline `language: system` hook philosophy.
- **Keep the residual, require container mode for markdown-heavy repos**: rejected — the deployment target (vault) is direnv-only by decision.

### Additional Context

Recon from the vault/exo-fleet deployment assessment (2026-07-17). Related: #1167, #1168, #883 (hook SSoT), #1099 (.pymarkdown preservation).

### Impact

- All direnv/bare consumers regain (or gain) markdown linting from the shared flake hook set; container/both lanes converge on the same system hook.
- Backward compatible (semver:minor). Consumers with the hand-managed YAML keep working; re-scaffold picks up the system-hook render.

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 11:35 AM_

Shipped via PR #1177, merged to `dev` (dev-PR `Closes` does not auto-close — closing manually). Reaches consumers with the next devkit release.

