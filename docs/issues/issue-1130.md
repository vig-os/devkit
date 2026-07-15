---
type: issue
state: closed
created: 2026-07-15T14:46:27Z
updated: 2026-07-15T15:21:27Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1130
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:00.766Z
---

# [Issue 1130]: [[BUG] Release finalize `Build release artifact` runs `just bundle` without `just sync` — bundler missing, exit 127](https://github.com/vig-os/devkit/issues/1130)

## Summary

The scaffolded **Release Core** workflow's `Build release artifact` step runs `just bundle` **without** a preceding `just sync`. For a JS-Action consumer, `bundle` → `npm run bundle` → `ncc …`, and `ncc` (`@vercel/ncc`) is a devDependency that only exists after `npm ci`. The devkit toolchain preamble provisions the dev-shell (node/npm/just/uv) but **not** the repo's `node_modules`, so the step fails:

```
just bundle → npm run bundle → sh: line 1: ncc: command not found
error: recipe `bundle` failed on line 85 with exit code 127
##[error]Process completed with exit code 127.
```

This only surfaces on a real `final` release (the step is gated on `release_kind == 'final' && has_bundle == 'true'`), where it trips the automatic rollback.

## This is an internal inconsistency, not a missing feature

Every other scaffolded job that runs `just bundle` already precedes it with `just sync` (the language-neutral install: `npm ci` for Node, `uv sync` for Python). The release finalize step is the lone exception:

| Workflow | Pattern |
|---|---|
| `dist-check.yml` | `just sync` → `just bundle` ✅ |
| `release-extension.yml` | `just sync` → `just bundle` ✅ |
| `ci.yml` | `just sync` before any build ✅ |
| **`release-core.yml` (Build release artifact)** | `just bundle` **only** ❌ |

## Fix

Add `just sync` before `just bundle` in the `Build release artifact` step of the `release-core.yml` scaffold template, mirroring `dist-check.yml` / `release-extension.yml`:

```yaml
- name: Build release artifact
  if: ${{ inputs.release_kind == 'final' && steps.bundle.outputs.has_bundle == 'true' }}
  run: |
    set -euo pipefail
    just sync      # install devDeps (npm ci / uv sync) so the bundler is on PATH
    just bundle
```

`just sync` is language-neutral and the step is already gated on `has_bundle`, so it stays a no-op for consumers without a bundle recipe.

## Regression source

Introduced by #1029 (opt-in `dist/` rebuild for node/TS consumers). The `just bundle` step was added to the release finalize job without the `just sync` that the sibling bundle-running jobs carry.

## Repro / impact

- Observed: vig-os/commit-action release 0.3.0 — run https://github.com/vig-os/commit-action/actions/runs/29423806600 (Finalize Release Core → Build release artifact → exit 127 → rollback).
- Impact: **every JS-Action consumer's `final` release rolls back** at finalization until the scaffold is fixed. Consumers can locally patch `release-core.yml` as a stopgap, but it is devkit-managed and will be clobbered on re-scaffold.

## Design note (open question — not part of this fix)

The scaffold couples to the artifact in two hardcoded spots beyond the recipe name: the `dist/` path in `release-core.yml` `FILE_PATHS` and the `git status -- dist/` checks in `dist-check.yml` / `release-extension.yml`. The recipe-presence convention (`just --summary | grep -qw bundle`) already gives consumers an extension point; the only remaining hardcoded coupling is the **output path**. If a consumer ever needs a non-`dist` layout, decoupling that path (e.g. a `.vig-os` `RELEASE_ARTIFACT_PATHS` key read by all three workflows) would be the minimal way to open it up. Likely YAGNI at the current consumer count — filed here only as context, not a requested change.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 03:21 PM_

Fixed by #1131 (merged into `dev`). The scaffolded `release-core.yml` `Build release artifact` step now runs `just sync` before `just bundle`, so a JS-Action consumer's bundler (`ncc`, a devDependency) is on PATH — matching the sync-then-build pattern of the other build jobs; no-op for consumers without a `bundle` recipe. Devkit's own `release.yml` has no bundle step, so no twin to mirror. Ships to consumers with the next devkit release; commit-action's 0.3.0 final re-run will be the live proof.

