---
type: issue
state: open
created: 2026-10-06T11:10:34Z
updated: 2026-10-10T21:24:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1843
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-11T08:37:37.702Z
---

# [Issue 1843]: [release-core finalize dispatches sync-issues.yml even when the sync-issues feature is disabled (final release impossible)](https://github.com/vig-os/devkit/issues/1843)

## What happens

With `release` enabled and `sync-issues` in `DEVKIT_FEATURES_DISABLED` (the solo profile disables `sync-issues`; re-enabling only `release` gives this combination), the scaffold removes `.github/workflows/sync-issues.yml`, but `release-core.yml` → **Finalize Release Core** still unconditionally runs:

- `Trigger sync-issues workflow` (`gh workflow run sync-issues.yml --ref release/X.Y.Z ...`)
- `Wait for sync-issues completion`, `Pull sync-issues changes`

The dispatch fails (`ERROR: Command failed after 2 attempts: gh workflow run sync-issues.yml --ref release/0.1.0 -f target-branch=release/0.1.0`), finalize fails, the rollback runs, and **no final release is possible**.

There is no supported way around it on the consumer side: patching `release-core.yml` trips the scaffold-drift gate, and a stub `sync-issues.yml` is removed by the scaffold for a disabled feature.

## Repro

1. Solo profile, then drop `release` from `DEVKIT_FEATURES_DISABLED` (keep `sync-issues`), re-render (1.18.0, trunk).
2. `prepare-release.yml -f version=0.1.0` → ok.
3. `release.yml --ref release/0.1.0 -f release-kind=final` → Finalize fails at the sync-issues dispatch.

## Expected

Either render the three sync-issues steps only when the feature is enabled (or guard them at runtime, e.g. on the workflow existing), or refuse the `release`-without-`sync-issues` combination at scaffold time with a clear message.

---

# [Comment #1]() by [c-vigo]()

_Posted on October 8, 2026 at 09:26 AM_

Hit this on 1.18.0 in a downstream consumer (trunk, `sync-issues` disabled). Interim workaround while the drift gate is off: guard **Trigger** and **Wait** on `hashFiles('.github/workflows/sync-issues.yml') != ''`. Keep **Pull sync-issues changes** unconditional: it is also what brings the API-pushed finalize commit into the checkout before `finalize_sha` is read. Skipping it would tag the pre-finalize commit.

---

# [Comment #2]() by [gerchowl]()

_Posted on October 10, 2026 at 09:24 PM_

One more trap for consumers who fix this by enabling `sync-issues`: GitHub only dispatches a workflow that already exists on the **default** branch. After the re-render merges into `dev`, `gh workflow run sync-issues.yml --ref release/X.Y.Z` still returns `HTTP 404: workflow sync-issues.yml not found on the default branch` until a release has carried the file to `main`. So the first release after enabling the feature still fails finalize. A runtime guard (skip when the workflow isn't registered) would cover both cases. Seen in gerchowl/claude-config#80.

