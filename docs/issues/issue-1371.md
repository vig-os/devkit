---
type: issue
state: closed
created: 2026-08-07T14:47:00Z
updated: 2026-08-07T16:00:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1371
comments: 1
labels: bug, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:59.837Z
---

# [Issue 1371]: [[BUG] CI Test Summary passes when a needed job is cancelled](https://github.com/vig-os/devkit/issues/1371)

## Summary

`Test Summary` (the `summary` job in `.github/workflows/ci.yml`) is the **only
required status check** on `dev`. It aggregates eight `needs:` jobs but sets
`FAILED=true` **only** when a job's `result` is `"failure"`. A **`cancelled`**
job therefore leaves the required check **green**, and a PR whose CI never
actually finished can be merged.

## Where

`.github/workflows/ci.yml`, job `summary` (`if: always()`), first step
"Check test results":

```bash
if [ "${{ needs.build-image.result }}" = "failure" ]; then
  echo "ERROR: Build image failed"
  FAILED=true
fi
```

…repeated for `build-image`, `test-image`, `test-integration`,
`project-checks`, `commit-checks`, `python-security`, `security-scan`,
`dependency-review`. None of the eight tests for `cancelled`.

## How a job gets `cancelled`

- job `timeout-minutes` elapses;
- a concurrency group cancels the in-progress run when a new commit is pushed —
  but the *old* run's `summary` still reports on the PR until the new one
  supersedes it;
- runner eviction / infrastructure cancellation;
- someone hits "Cancel workflow" on a run.

In each case `summary` itself still executes (`if: always()`), finds no
`"failure"`, prints "All executed test suites passed", and exits 0.

## Fix

For each of the eight needed jobs, set `FAILED=true` when the result is
`"failure"` **or** `"cancelled"`.

## Explicitly NOT fixed on `skipped`

`skipped` must stay tolerated: `workflow_dispatch` accepts a `test-suite`
input (`all` / `image` / `integration` / `project`) and every job is gated on it,
so a deliberate subset run legitimately skips the rest. `commit-checks` and
`dependency-review` are also PR-only. Failing on `skipped` would break both.

The precedent is pinned for the **scaffold** copy by
`tests/test_workflow_private_repo_guard.py::test_summary_needs_dependency_review_with_skip_tolerance`;
this issue changes only devkit's **own** `ci.yml`, which is not
manifest-synced to `assets/workspace/`.

## Acceptance criteria

- [ ] each of the eight `needs:` jobs trips `FAILED` on `cancelled` as well as
      `failure`
- [ ] no job trips `FAILED` on `skipped`
- [ ] the per-job echo/reporting style of the step is unchanged
- [ ] the skipped-is-legitimate rationale is recorded in a comment in the
      workflow

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 03:59 PM_

Fixed on dev by PR #1375 (51f92a6d): all eight needed jobs in the Test Summary gate now trip FAILED on cancelled as well as failure, with skipped still tolerated (rationale recorded in a workflow comment) — pinned by the new bats test from 6420af3f.

