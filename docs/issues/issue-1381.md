---
type: issue
state: closed
created: 2026-08-07T16:21:18Z
updated: 2026-08-07T16:38:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1381
comments: 1
labels: bug, priority:low, effort:small, area:testing
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:56.856Z
---

# [Issue 1381]: [[BUG] githooks.bats does not isolate IN_NIX_SHELL, fails when run from a nix develop shell](https://github.com/vig-os/devkit/issues/1381)

## Summary

The `githooks.bats` tests that assert the workspace githook guard *blocks*
outside a devcontainer only sanitize `IN_CONTAINER` (`env -u IN_CONTAINER`).
The guard itself, however, also legitimately passes when `IN_NIX_SHELL` is set.
Running the suite from a `nix develop` shell (where `IN_NIX_SHELL=impure` is
exported) therefore fails 9 of the 12 `githooks.bats` tests, even though the
code under test is behaving correctly.

## Evidence

Observed 2026-08-07 while validating #1377: full bats run from a nix shell →
575/584 passed with all 9 failures in `githooks.bats`; re-run with
`IN_NIX_SHELL` unset → `githooks.bats` 12/12 passed. CI is unaffected (its
environment does not export `IN_NIX_SHELL`), so this is a local-DX trap only.

## Fix

Extend the environment sanitization in the affected `githooks.bats` cases to
also unset `IN_NIX_SHELL` (mirroring the existing `env -u IN_CONTAINER`
handling), so the suite is deterministic regardless of the invoking shell.

## Related

Surfaced while validating #1377 (PR #1379).

Refs: #1377
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 04:38 PM_

Fixed on dev by PR #1384: the nine guard-blocking cases in tests/bats/githooks.bats now unset IN_NIX_SHELL alongside the existing IN_CONTAINER sanitization, so the suite is deterministic regardless of the invoking shell. Verified failing 9/12 with IN_NIX_SHELL=impure before the change and 12/12 after, both with and without the variable set.

