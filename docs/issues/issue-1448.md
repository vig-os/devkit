---
type: issue
state: closed
created: 2026-08-12T09:09:59Z
updated: 2026-08-12T09:49:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1448
comments: 1
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:40.151Z
---

# [Issue 1448]: [[FEATURE] Ship a doctor recipe on the consumer surface (host preflight for scaffolded repos)](https://github.com/vig-os/devkit/issues/1448)

### Description

`just doctor` (added in #1418, extended with a `core.hooksPath` diagnostic in #1430) exists **only in devkit's own `justfile`**. The scaffolded consumer surface (`assets/workspace/justfile`, `assets/justfile.d`) ships no equivalent, so a consumer clone gets no host preflight at all.

That is the same gap #1430 described, in the population devkit actually ships to. A consumer contributor who clones outside the devcontainer has no way to ask whether their git identity, commit signing, ssh-agent, `gh` auth, or — most importantly — `core.hooksPath` are wired. The hooks are tracked and inert, and nothing tells them.

### Proposed Solution

Ship a `doctor` recipe on the consumer surface, modelled on devkit's own (`justfile`, `[group('info')]`):

- Diagnostics only: `PASS` / `WARN` lines, **always exits 0**. It is not a gate.
- Report the same host prerequisites devkit's does — git identity, commit signing, ssh-agent, `gh` auth — plus the `core.hooksPath` check from #1430.
- Consumers come in two modes: the devcontainer sets `core.hooksPath` during setup, and the direnv / `nix develop` dev shell sets it on shell entry via `githooksPathHook` (#1112). The recipe must give a sensible verdict in both, and in an ad-hoc checkout outside both.

Scope notes:

- This is a new consumer-facing recipe, so it needs its own manifest/sync wiring and bats coverage — it is not a copy-paste of devkit's block.
- Devkit's own `doctor` remains the SSoT for the diagnostic logic where sharing is practical; avoid two drifting implementations of the same checks (the layered `justfile` model is `.devcontainer/justfile.base` managed → `justfile.project` team-shared → `justfile.local` personal; a shared recipe belongs in the managed base, never in `justfile.project`).
- The remediation hint differs by mode: devkit's says `./scripts/init.sh`, which is not the consumer's entry point.

### Alternatives Considered

Leaving it devkit-only, which is the status quo. Rejected because the failure mode #1430 documents ("configured, believed active, never executed") is strictly worse in consumer repos, where the person committing is least likely to know devkit's installer exists.

### Additional Context

Surfaced while closing #1430, where the fix was deliberately scoped to devkit's own `justfile` under YAGNI / minimal-diff. This is the consumer half, filed separately as agreed there.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 09:49 AM_

Implemented by #1451, merged to `release/1.8.0` as f49c645b (ships in 1.8.0-rc2).

`just doctor` now ships in the scaffolded root `justfile` — the only managed justfile layer present in every delivery mode (`direnv`/`bare` carry no `.devcontainer/`, and `justfile.project` is a `PRESERVE_FILES` entry, so a recipe there would never reach an existing consumer on upgrade). Diagnostics only: `PASS`/`WARN`, always exits 0.

**Mode-aware remediation.** Devkit's hint is `./scripts/init.sh`, a file no consumer has. The consumer hint is driven by `DEVKIT_MODE` in `.vig-os`, universal command first, mode entry point named on top:

| mode | inert-hooks WARN tail |
|---|---|
| `direnv` | `(run: git config core.hooksPath .githooks); normally set on dev-shell entry: run direnv allow` |
| `devcontainer` | `(run: …); normally set by the devcontainer setup: reopen the container` |
| `both` | `(run: …); normally set by the devcontainer setup (reopen the container) or on dev-shell entry (direnv allow)` |
| `bare` / no `.vig-os` | `(run: git config core.hooksPath .githooks)` — nothing wires it, so no entry point is named |

`./scripts/init.sh` never appears in any mode, and that is test-enforced. Verified by running the real `assets/init-workspace.sh --no-prompts --mode <mode>` in three modes and invoking the recipe against the produced trees.

**Sharing vs duplication — two implementations, drift pinned by a test.** Three sharing routes were evaluated and rejected: a synced shared script (needs a brand-new always-shipped managed root path, since `.devcontainer/` is absent in direnv/bare and there is no scaffolded root `scripts/`); a manifest transform (`scripts/manifest.toml` transforms whole files, so splicing one recipe from A into B needs a new transform type bought for a single recipe); and importing devkit's justfile (never scaffolded). The recipes also genuinely differ in behavior, not just wording. Instead of forcing the abstraction, the shared *contract* is pinned: `consumer doctor checks exactly what devkit's doctor checks` runs both recipes under one controlled environment and asserts the check-label sets are non-empty and identical, so adding a check to one and not the other now fails CI.

No manifest/sync wiring was needed — `assets/workspace/justfile` is authored directly in the scaffold tree, rsynced from `TEMPLATE_DIR`, and already in the never-migrate managed literal list (`assets/init-workspace.sh:1124`); this adds no `.vig-os` knob, it only reads the existing `DEVKIT_MODE`.

Evidence: `bats tests/bats/` 496 ok / 0 failures; `prek run --all-files` exit 0; `test_flake_hooks` 63 passed post-merge.

Follow-up filed as #1454: neither doctor special-cases linked worktrees, so both report hooks inert inside a `worktree-start` worktree where they are live.

