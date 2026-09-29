---
type: issue
state: open
created: 2026-09-28T11:50:09Z
updated: 2026-09-28T11:50:09Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1745
comments: 0
labels: bug, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:55.686Z
---

# [Issue 1745]: [[BUG] Release train deadlocks on its own Dist Check: the bundle rebuild is final-only and downstream of the candidate's check gate](https://github.com/vig-os/devkit/issues/1745)

## Description

For a consumer with a committed build artifact (a bundled GitHub Action:
`dist/index.js` via `just bundle`), the release train can **deadlock** on its own
`Dist Check` gate before the step that would resolve it ever runs.

The three pieces, all in the managed scaffold:

1. **`dist-check.yml`** triggers on `pull_request` to `release/**` and `main`
   only. `dev` is deliberately *not* dist-gated, so Renovate lockfile bumps
   merge to `dev` without regenerating the bundle. That is by design and fine.
2. **`release-core.yml`** rebuilds and commits the bundle in the finalize
   commit — `just bundle` + `FILE_PATHS: CHANGELOG.md,<dist_paths>` — but the
   step is gated `if: ${{ inputs.release_kind == 'final' && ... }}`.
3. **`release-core.yml` validate** refuses to proceed when any latest check on
   the release PR is red:

   ```
   CI_FAILED=$(echo "$LATEST_CHECKS" | jq '[.[] | (.conclusion // .state) as $v | select($v == "FAILURE" or $v == "ERROR")] | length')
   if [ "$CI_FAILED" != "0" ]; then
     echo "ERROR: PR #$PR_NUMBER has failed CI checks"
     exit 1
   ```

`prepare-release.yml` opens the draft `release/X.Y.Z -> main` PR, which
immediately triggers `Dist Check` against the bundle as it stands on `dev` —
stale, because of (1). `release.yml candidate` then hits (3) and aborts, so the
finalize rebuild in (2) never runs. And even if the gate let it through, (2) is
`final`-only, so the candidate would still never refresh the bundle.

Net effect: the artifact must be fresh **before the candidate**, even though
every other part of the design treats release time as the authority on bundle
freshness (`release-extension.yml`'s `verify-dist` re-checks it at the finalize
SHA). The consumer-visible symptom is a red release PR on a train where nothing
is actually wrong with the source.

## Steps to Reproduce

In a Node/TS consumer with a `bundle` recipe and a committed `dist/`:

1. Let Renovate merge one or more lockfile/dependency PRs to `dev` (they touch
   `package-lock.json`, never `dist/`, and `dist-check.yml` does not run on
   `dev`-targeted PRs).
2. `gh workflow run prepare-release.yml -f version=X.Y.Z` — the draft release PR
   opens and `Dist Check` fails on it.
3. `gh workflow run release.yml` (candidate) — validate aborts with
   `ERROR: PR #N has failed CI checks`.

## Expected Behavior

A train started from a `dev` whose source is sound should run clean. Either:

- **(a)** rebuild + commit the bundle at **prepare** time (or for the
  candidate, not just `final`), so the artifact is fresh by the time
  `Dist Check` first evaluates the release PR; or
- **(b)** have the candidate's check gate ignore `Dist Check` specifically,
  since finalize regenerates the bundle regardless and
  `release-extension.yml`'s `verify-dist` is the real publishing gate.

(a) is the more honest fix — the rc then genuinely reflects what ships. (b) is
the smaller diff.

## Actual Behavior

The candidate aborts on a red `Dist Check` that only the (final-only,
downstream) finalize step can clear. The documented recovery is a manual
`bugfix/<issue>-...` branch off `release/X.Y.Z` that rebuilds the bundle, PRs
into the release branch, merges, then re-dispatches the candidate — a mid-train
detour on every train that follows a batch of dependency bumps.

## Environment

- **Consumer**: `vig-os/sync-issues-action` (Node/TS action, `direnv` mode,
  `DEVKIT_VERSION=1.17.0`, gitflow)
- **Devkit**: 1.17.0
- **Observed**: 2026-09-28, preparing `v0.5.1`

Concretely: `dev` sat 76 commits past `v0.5.0` with `dist/index.js`
byte-identical to the `v0.5.0` tag, while the lockfile had moved on —
the committed bundle embedded `@octokit/auth-app` 8.3.0 / core 10.0.13 /
request 7.0.7 against locked 8.3.1 / 10.0.16 / 7.0.8, plus `@vercel/ncc`
0.44 -> 0.45 output churn. A local `npm ci && npm run bundle` reproduced
`Dist Check`'s verdict exactly (+760/-377 in `dist/index.js`).

This is the second occurrence in this repo: the `v0.4.0` train hit the same wall
on a stale `ncc` bundle from a Renovate bump and was recovered with the manual
bugfix-into-release-branch detour.

## Additional Context

Contrast with how the changelog side was solved: `prepare-release.yml` runs
`synthesize-bot-changelog` at **prepare** time, so bot-authored dependency and
adoption PRs that never touched `CHANGELOG.md` on `dev` are reconciled before
the content gate evaluates. The bundle has the identical shape of problem — bot
PRs that legitimately skip a managed artifact on `dev` — but no equivalent
prepare-time reconciliation, so it fails a gate instead.

