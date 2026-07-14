---
type: issue
state: closed
created: 2026-07-14T11:30:30Z
updated: 2026-07-14T15:13:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1059
comments: 1
labels: feature, priority:medium, area:ci, area:workflow, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:25.469Z
---

# [Issue 1059]: [[FEATURE] prepare-release extension hook (prepare-release-extension.yml) — mutating counterpart to release-extension](https://github.com/vig-os/devkit/issues/1059)

## Description

Add a **project extension hook to `prepare-release.yml`**, mirroring the one `release.yml` already has: a scaffolded `prepare-release-extension.yml` reusable workflow (default no-op) that consumers replace with project-specific release-branch preparation — the *mutating* counterpart to the read-only `release-extension.yml`.

## Problem Statement

Two independent consumers of the prepare phase need a project-specific step, and today both have to solve it badly:

1. **Devkit itself.** Devkit's own `prepare-release.yml` runs a hardcoded project step — `uv run python scripts/sync_manifest.py sync assets/workspace/` (`.github/workflows/prepare-release.yml:210`, and again in the rollback restore at `:391`) — that is absent from the scaffold copy shipped to consumers. Devkit's own prepare workflow is therefore a **permanent divergence from its own template**, precisely the situation the release-extension hook was introduced to eliminate for `release.yml`.

2. **Action-publishing consumers** (`vig-os/commit-action`). The committed `dist/index.js` must be fresh on every tagged commit. The existing `release-extension.yml` hook runs **after** `finalize_sha` is computed and before `release-publish` tags it, so it can only *verify* — it cannot add a rebuild commit that would be included in the tag. commit-action therefore scoped its CI dist gate to the release boundary (commit-action#71) and accepted a manual flow: when `dev` has drifted (e.g. Renovate runtime-dep bumps), the `release/X.Y.Z → main` draft PR fails Dist Check and a human must push a `bugfix → release/*` rebuild PR. A prepare-time hook would close that loop: rebuild + commit on the freshly cut release branch, automatically.

The structural gap: `release.yml` has a designed extension point; `prepare-release.yml` — the only other phase where project-specific work naturally occurs — has none.

## Proposed Solution

- New scaffolded reusable workflow `prepare-release-extension.yml` (`on: workflow_call`), default no-op, same pattern as `release-extension.yml`.
- `prepare-release.yml` calls it from the `prepare` job's failure domain, **after the `release/X.Y.Z` branch is created and before the draft PR to `main` is opened**, so any commits the extension pushes appear in the PR diff from the start.
- Inputs: `version`, the release branch name, the post-freeze branch head SHA, `dry-run`, and the git user name/email inputs prepare-release already carries. `secrets: inherit`, so the extension can mint the COMMIT_APP token to push to the write-protected release branch (the bypass already exists for exactly this — the changelog-freeze commit uses it).
- Semantics:
  - `dry-run: true` ⇒ the default no-op prints its inputs; consumer extensions must honor it (no writes).
  - Extension failure fails the `prepare` job ⇒ the **existing rollback** applies unchanged (delete the partial release branch, restore `CHANGELOG.md` on `dev`). No new rollback machinery needed — everything the extension commits lives on the branch that rollback deletes.
  - Anything the extension commits is ordinary release-branch history, re-validated by the rest of the pipeline (CI on the draft PR, RC candidates, finalize).
- Dogfooding: devkit moves the `sync_manifest.py` step (and its rollback-restore twin) out of its diverged `prepare-release.yml` into its own `prepare-release-extension.yml`, making its prepare workflow scaffold-verbatim again.

## Alternatives Considered

- **Consumer-local edits to the scaffolded `prepare-release.yml`**: permanent drift, re-patched on every devkit upgrade — the anti-pattern the release-extension hook exists to avoid.
- **Doing the work in `release-extension.yml`**: runs too late by design; the tag pins `finalize_sha`, so a commit added there is never tagged. Verified in practice while implementing commit-action's dist gate.
- **Keeping the work on `dev`** (e.g. gating every dev PR): tried in commit-action#59, reverted in commit-action#71 — it failed every Renovate runtime-dep bump for zero shipping benefit, since nothing ships from `dev`.
- **A generic "run this just recipe if present" convention** (e.g. `just release-prepare-hook`) instead of a reusable workflow: simpler, but loses the per-project job structure, permissions/secrets scoping, and the ability to use composite actions — and breaks the symmetry with `release-extension.yml`.

## Additional Context

- Concrete first consumer: `vig-os/commit-action` would implement the hook as: check out `release/X.Y.Z`, `just sync && just bundle`, and if `dist/index.js` is dirty, commit it via `vig-os/commit-action` itself with the COMMIT_APP token (same identity and mechanism as the changelog-freeze commit). Its `Dist Check` on the release PR then becomes pure verification of the hook.
- Composes cleanly with #1044 (`DEVKIT_TAG_PREFIX`) and #1045 (`DEVKIT_FLOATING_TAGS`) — no interaction; the hook runs long before tagging.
- Related: vig-os/commit-action#59, vig-os/commit-action#71 (the friction this removes), #1046 (downstream release doc — the hook contract belongs in `DOWNSTREAM_RELEASE.md` alongside the release-extension contract).

## Impact

- Backward compatible: the scaffolded default is a no-op; existing consumers see no behavior change until they replace it.
- Devkit removes a divergence between its own workflow and its scaffold.
- Action-publishing consumers get a fully hands-off release flow for committed build artifacts.
- SemVer: minor (new scaffold capability).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 03:13 PM_

Implemented in #1067 (merged to dev): scaffolded prepare-release-extension.yml (workflow_call no-op, preserved file), called between release-branch creation and PR-open so extension commits ride the existing rollback domain; devkit dogfoods it (sync_manifest divergence removed, job DAG test-pinned identical to the scaffold) and additionally reconciles dev's changelog mirror with a documented per-path failure analysis. Hook contract documented in DOWNSTREAM_RELEASE.md with the commit-action dist-rebuild example as the first consumer.

