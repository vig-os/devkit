---
type: issue
state: open
created: 2026-06-22T09:52:07Z
updated: 2026-06-22T09:52:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/612
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-22T20:15:51.824Z
---

# [Issue 612]: [[BUG] Smoke-test dispatch not idempotent across candidate→final on same base version](https://github.com/vig-os/devcontainer/issues/612)

## Description

The smoke-test dispatch orchestration is **not idempotent** when a base version is
released through both a candidate pass (`X.Y.Z-rcN`) and a final pass (`X.Y.Z`). On the
final pass the `## [X.Y.Z]` CHANGELOG heading gets dated **before** `release-core`
validation runs, which then fails because it requires the `## [X.Y.Z] - TBD` placeholder.

The defect lives in this repo even though it manifests downstream:

- `.github/workflows/repository-dispatch.yml` is a **synced template** consumed by
  `devcontainer-smoke-test`; the source/fix belongs here.
- `prepare-changelog` (`packages/vig-utils/src/vig_utils/prepare_changelog.py`) provides
  the `prepare`/`finalize` semantics involved: `finalize` requires a `- TBD` entry and is
  **not idempotent** (`prepare_changelog.py:386-390`), and `prepare` stacks a new heading
  without deduping an existing one.

## Observed (0.3.7)

`publish-candidate 0.3.7` then `finalize-release 0.3.7` were run against the same base
version. The final downstream smoke-test failed at "Release Core / Validate Release Core":

```
ERROR: CHANGELOG.md does not contain '## [0.3.7] - TBD'
```

CHANGELOG history on the reused `release/0.3.7` branch (smoke-test):

| Commit | Effect on `[0.3.7]` heading |
|--------|------------------------------|
| freeze (RC dispatch)  | created `## [0.3.7] - TBD` |
| deploy (final dispatch) | dated it → `## [0.3.7](…) - 2026-06-22` |
| validate | requires `- TBD` → exit 1 |

A secondary failure mode also appears: the `deploy` idempotency check
(`grep -q "Smoke-test deploy of <tag>"`) matches a bullet left inside the stale `[X.Y.Z]`
section, so `Unreleased` is not re-seeded and `prepare-release` aborts on an empty
Unreleased (same class as the already-fixed smoke-test #157).

## Root cause

The listener re-runs the whole `deploy → prepare-release → release → promote`
orchestration on **every** dispatch against a **reused** `release/X.Y.Z` branch and a
per-base-version CHANGELOG entry a prior candidate pass already froze.

## Proposed fix (directions)

- Reset the target version entry to `## [X.Y.Z] - TBD` (or recreate `release/X.Y.Z` from
  a clean `dev`) at the start of each dispatch, making candidate→final on one base version
  idempotent.
- Make `prepare-changelog finalize` a no-op when the entry is already dated for the same
  version.
- Scope the `deploy` idempotency check to the `Unreleased` section, not the whole file.
- Re-sync the template to `devcontainer-smoke-test` after fixing here.

## Refs

Downstream tracking issue: vig-os/devcontainer-smoke-test#169
Recovery for 0.3.7 performed manually (dev CHANGELOG reset + stale branch delete + re-dispatch).

