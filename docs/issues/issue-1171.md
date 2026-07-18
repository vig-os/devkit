---
type: issue
state: closed
created: 2026-07-17T09:57:03Z
updated: 2026-07-17T11:35:52Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1171
comments: 1
labels: feature, priority:high, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:26.757Z
---

# [Issue 1171]: [Nix consumer support: language detection, statix/deadnix on the consumer hook surface, nix gitignore fragment](https://github.com/vig-os/devkit/issues/1171)

### Description

Treat Nix as a first-class consumer language in the scaffold: detect nix-oriented repos, ship a `nix` gitignore fragment, and make `statix`/`deadnix` available on the consumer hook surface (today they are devkit-internal gates only).

### Problem Statement

Three nix-oriented consumers are now in the deployment queue — `exo-pet/exo-fleet` (NixOS fleet, 72 .nix files), `Personal/vigo-nixos` (46 .nix files), and devkit itself — which clears the ask-gate (`nix/modules/default.nix` YAGNI policy) for nix support. Today:

- Language detection (`assets/init-workspace.sh`) knows `pyproject.toml`→python, `package.json`→node, `Cargo.toml`→rust — but nothing for nix, so nix repos get no language gitignore fragment.
- `statix` and `deadnix` run only as devkit-internal `nix flake check` gates scoped to `./flake.nix` + `./nix` — they are not in the consumer hook set, so nix consumers can't get them without hand-rolling custom hooks. exo-fleet runs both today via devenv git-hooks and would lose them on migration.

### Proposed Solution

- **Detection**: a repo is nix-oriented when it has `*.nix` files **beyond the scaffold-managed `./flake.nix`** (excluding `.git/`, `.direnv/`, `.worktrees/`). NOTE the trap: `flake.nix` alone cannot be the marker — every direnv scaffold ships one, so re-scaffold re-detection would false-positive on all direnv consumers. The beyond-flake.nix rule is deterministic and re-scaffold-safe (vault/commit-action: 0 extra .nix → not nix; exo-fleet/vigo-nixos: many → nix).
- **Gitignore fragment**: `assets/gitignore.d/nix.gitignore` (`result`, `result-*`) wired into the detection→fragment mapping like rust.
- **Hooks**: add `statix` and `deadnix` binaries to `nix/devtools.nix` and define them in `nix/hooks.nix` hookDefs as `language: system` hooks on the **flake-generated consumer surface only** (`scaffold = false` — not injected into the committed hand-managed YAML, so existing container-mode consumers see no behavior change until they opt into flake hooks). Mirror devkit's own gate settings/excludes. The scaffolded/template consumer `flake.nix` must itself pass both linters (deadnix is prone to flagging intentionally-unused lambda args — configure accordingly).
- **CodeQL**: no matrix change (nix is not a CodeQL language — same treatment as rust); detection must not disturb `render_codeql_matrix`.

### Alternatives Considered

- A `nix` capability module (ADR-capability-modules): wrong shape — nix consumers already have nix in the base toolchain; what they lack is hooks + statics, which the module contract (packages+env+shellHook) doesn't carry.
- Enabling statix/deadnix `scaffold = true` for everyone: rejected — would surprise all existing consumers' hand-managed YAML on next re-scaffold.

### Additional Context

Recon from the exo-fleet/vigo-nixos deployment assessment (2026-07-17). exo-fleet also migrates nixpkgs-fmt → nixfmt-rfc-style (org standard, already shipped) — consumer-side, one-time reformat, not in scope here. Related: #1024/#1025 (language-aware statics), ADR-capability-modules.

### Impact

- Nix consumers get result-symlink hygiene and the statix/deadnix lint pair from the shared flake hook set; non-nix consumers unaffected.
- Backward compatible (semver:minor).

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 11:35 AM_

Shipped via PR #1176, merged to `dev` (dev-PR `Closes` does not auto-close — closing manually). Reaches consumers with the next devkit release.

