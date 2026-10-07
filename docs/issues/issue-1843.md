---
type: issue
state: open
created: 2026-10-06T11:10:34Z
updated: 2026-10-06T11:10:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1843
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-07T08:29:21.009Z
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

