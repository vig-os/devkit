---
type: issue
state: closed
created: 2026-08-07T13:04:43Z
updated: 2026-08-07T15:59:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1365
comments: 2
labels: chore, priority:high, area:ci, effort:medium, semver:minor
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:01.638Z
---

# [Issue 1365]: [Switch stamped workflows to client-id App credentials (next release)](https://github.com/vig-os/devkit/issues/1365)

## Context

A 2026-08-07 audit of GitHub-App credentials across `vig-os` and `exo-pet` found
that every App secret pair can be consolidated to **Client ID only**. Nothing in
the auth path is numerically load-bearing: `@octokit/auth-app` accepts a
client-ID string (`Iv23li…`) wherever it accepts a numeric App ID, on every
pinned action version currently in use.

devkit already went client-ID-only for the Release App and for most of the
Commit App. Two stamped workflows are the remaining holdouts, and because they
are stamped, they keep numeric `*_APP_ID` secrets alive in **every consumer
repo** in both orgs. Retiring the org secrets is blocked until this ships.

## Scope — exact references

### 1. `assets/workspace/.github/workflows/sync-issues.yml`

- **`:177`** — `app-id: ${{ secrets.COMMIT_APP_ID }}` passed to
  `vig-os/sync-issues-action@285a0af…` (v0.4.0, `:175`).
- Change to `client-id: ${{ secrets.COMMIT_APP_CLIENT_ID }}` **and** bump the
  action pin, once vig-os/sync-issues-action#168 ships the `client-id` input.
- `COMMIT_APP_CLIENT_ID` already exists as an org secret in both orgs — no new
  secret is needed for this half.

### 2. `assets/workspace/.github/workflows/devkit-upgrade.yml`

- **`:11`** — header comment naming `DEVKIT_UPGRADE_APP_ID`.
- **`:54-61`** — the "Require the upgrade App identity" preflight reads
  `APP_ID: ${{ secrets.DEVKIT_UPGRADE_APP_ID }}` into env (`:55`), gates on it
  (`:59`), and names it in the `::error::` message (`:60`).
- **`:66-68`** — `actions/create-github-app-token@bcd2ba49…` (v3) with
  `app-id: ${{ secrets.DEVKIT_UPGRADE_APP_ID }}`.
- Rename the secret to **`DEVKIT_UPGRADE_APP_CLIENT_ID`** and switch the action
  input to `client-id:`. The pinned `create-github-app-token` is v3, which is
  at or above v3.1.0 — the release that introduced `client-id` — so no action
  bump is required here; confirm against the pinned SHA before landing.

### 3. `tests/test_workflow_devkit_upgrade.py`

- **`:14`** and **`:129`** — docstrings naming `DEVKIT_UPGRADE_APP_ID`.
- **`:132`** — `assert "secrets.DEVKIT_UPGRADE_APP_ID" in text` must become the
  client-ID name. `:133` (`_PRIVATE_KEY`) is unchanged.

### 4. Docs

- **`docs/RELEASE_CYCLE.md:608`** — the COMMIT_APP row still carries the
  parenthetical "`COMMIT_APP_ID` still required by `vig-os/sync-issues-action`
  in `sync-issues.yml`". Drop it, and rename the DEVKIT_UPGRADE entry.
- **`docs/DOWNSTREAM_RELEASE.md:124`** — `COMMIT_APP_ID` (required by
  `vig-os/sync-issues-action` in `sync-issues.yml`) in the required-secrets list.
- **`docs/security/ADR-secrets-management.md:56`** — the COMMIT_APP row lists
  `COMMIT_APP_ID` among the consumed secrets.

(Files under `docs/issues/` and `docs/pull-requests/` are synced historical
records — leave them alone.)

## Sequencing — read before scheduling

The order is load-bearing, and getting it wrong breaks consumers:

1. **vig-os/sync-issues-action#168 ships first.** No `client-id` input, no
   sync-issues change.
2. **`DEVKIT_UPGRADE_APP_CLIENT_ID` org secrets must exist in BOTH `vig-os` and
   `exo-pet` *before* any consumer adopts the release.** The preflight at
   `devkit-upgrade.yml:54-61` hard-fails without it, which would brick the very
   automation that delivers the upgrade. Config-first, always. The exo-pet side
   is tracked in exo-pet/org-config#1; the vig-os side is tracked in
   `vig-os/org-config` under an existing tracker being re-scoped separately.
3. **Old numeric secrets are deleted only after the last consumer upgrades.**
   Migration principle: *no numeric `*_APP_ID` secret is deleted while any
   pinned workflow still references it.* Cautionary precedent —
   `exo-pet/playground-carlos`'s sync-issues job broke **silently for a week**
   when `COMMIT_APP_ID` was unavailable; the job kept reporting success while
   syncing nothing.

### Consumer readiness

- Repos already on devkit **1.6.0** ride `devkit-upgrade.yml` automation and
  pick this up without manual work (`exo-pet`: exo-fleet, vault,
  playground-carlos).
- Two repos are on old scaffolds and need a bump **before** they can benefit:
  - vig-os/h5v#6 — 0.3.1-era scaffold, 13 numeric-ID references.
  - vig-os/scitadel#208 — 0.3.3-era scaffold (bump itself tracked in
    vig-os/scitadel#207) plus a repo-local release-please bot.
- vig-os/tessera#363 deliberately uses its own App and does **not** consume this
  scaffold for its credentials — it migrates independently.

## Acceptance criteria

- [ ] `sync-issues.yml` scaffold passes `client-id` + `COMMIT_APP_CLIENT_ID` and
      pins the sync-issues-action release from vig-os/sync-issues-action#168.
- [ ] `devkit-upgrade.yml` scaffold uses `DEVKIT_UPGRADE_APP_CLIENT_ID` in the
      preflight, the error message, the header comment, and the `client-id:`
      input.
- [ ] `tests/test_workflow_devkit_upgrade.py` asserts the new names and passes.
- [ ] The three docs above no longer state that a numeric App ID is required.
- [ ] Release notes call out the new required org secret **and** the ordering
      rule (create the secret before upgrading), prominently enough that a
      consumer cannot miss it.
- [ ] No numeric `*_APP_ID` reference remains in `assets/workspace/`.

## Open question for triage

Renaming a **required** secret in a stamped workflow is breaking for any
consumer that upgrades before the org secret exists — the preflight fails hard.
No `semver:` label has been applied here on purpose: please decide whether this
rides a minor with a loud release note, or warrants a major. A backward-compatible
fallback (accept either secret name for one release, warn on the old one) would
keep it minor and is worth considering.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 01:08 PM_

Cross-reference correction — the sibling issues filed alongside this one landed with these numbers:

- vig-os/sync-issues-action#168 — prerequisite (`client-id` input)
- vig-os/h5v#6 — old-scaffold repo, needs a bump first
- vig-os/scitadel#209 — old-scaffold repo (the bump itself is vig-os/scitadel#207)
- vig-os/tessera#364 — dedicated App, migrates independently
- exo-pet/org-config#20 — exo-pet org-secret creation and retirement

The body above was written before the last three numbers were known; where it says scitadel#208, tessera#363, or org-config#1, use the numbers in this list.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 7, 2026 at 03:59 PM_

Fixed on dev by PR #1373 (43dbce3b): both stamped workflows (sync-issues.yml, devkit-upgrade.yml) now pass client-id App credentials, with a backward-compatible fallback to the legacy numeric secret in devkit-upgrade.yml so the rename rides a minor. Ships with the next release. Fallback removal and org-secret retirement tracked in #1366.

