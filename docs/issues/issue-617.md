---
type: issue
state: closed
created: 2026-06-22T12:26:15Z
updated: 2026-06-22T21:04:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/617
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T06:15:17.393Z
---

# [Issue 617]: [[BUG] prepare-release can branch release/X.Y.Z at pre-freeze dev SHA (read-after-write race)](https://github.com/vig-os/devcontainer/issues/617)

## Description

`prepare-release` can create the `release/X.Y.Z` branch at the **pre-freeze** dev
SHA, producing a release branch whose CHANGELOG lacks `## [X.Y.Z] - TBD`. The
`Release` workflow then fails at "Validate Release → Verify CHANGELOG has TBD
entry" with `ERROR: CHANGELOG.md does not contain '## [X.Y.Z] - TBD'`.

## Observed (0.3.8)

Within the successful `Prepare Release` run `27949666239`:

| Time (UTC) | Step | dev SHA |
|---|---|---|
| 11:34:42 | Capture pre-prepare dev SHA | `a1e787c` (pre-freeze) |
| 11:34:44 | Commit freeze to dev (commit-action) | creates `0a9334d` |
| 11:34:45 | Create release branch from dev | re-read dev → **`a1e787c`** (stale) → branched here |

`dev` correctly advanced to `0a9334d` (single `## [0.3.8] - TBD`), but
`release/0.3.8` was cut at `a1e787c`. The downstream `Release` run `27950027799`
then failed validation. (Recovery: fast-forward `release/0.3.8` → `dev`, re-run.)

## Root cause

The "Create release branch from dev" step re-reads `dev`'s ref and branches from
whatever it returns:

```bash
DEV_SHA=$(retry ... gh api "repos/$REPO/git/ref/heads/dev" --jq '.object.sha')
```

GitHub's REST ref read is **not strongly consistent immediately after a write**:
~1s after commit-action pushes the freeze, the read can still return the
pre-freeze SHA. The `retry` wrapper only retries on **failure** — a stale but
*successful* read passes through. Nothing asserts that dev actually advanced past
the captured pre-freeze SHA (`prepare_start_sha`), so a stale branch is created
silently and the failure only surfaces two steps later in `Release`.

## Proposed fix

In the create-branch step, **poll dev until its SHA differs from
`prepare_start_sha`** (with backoff), and hard-fail if it never advances; branch
from that confirmed post-freeze SHA. `prepare_start_sha` is already captured and
output by the pre-state step.

Apply to both copies (identical pattern):
- `.github/workflows/prepare-release.yml` (this repo's own release)
- `assets/workspace/.github/workflows/prepare-release.yml` (synced workspace template)

## Refs

Surfaced while validating #612 (0.3.8 release). Distinct root cause (branch-creation
read-after-write race), not the smoke-test dispatch idempotency fixed there.

---

# [Comment #1]() by [c-vigo]()

_Posted on June 22, 2026 at 09:04 PM_

Fixed via #618 and shipped in [0.3.8](https://github.com/vig-os/devcontainer/releases/tag/0.3.8). The prepare-release "Create release branch from dev" step now polls dev until it advances past the captured pre-freeze SHA before branching. Validated end-to-end by the 0.3.8 candidate→final release runs.

