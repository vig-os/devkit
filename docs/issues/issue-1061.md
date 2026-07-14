---
type: issue
state: closed
created: 2026-07-14T11:46:46Z
updated: 2026-07-14T12:29:24Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1061
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:24.629Z
---

# [Issue 1061]: [[BUG] CI never runs the lightweight shape-test suites — Project Checks pytest scope is a stale explicit list](https://github.com/vig-os/devkit/issues/1061)

## Problem

`.github/actions/test-project/action.yml` (the `Project Checks` job, suite: all) runs exactly `tests/test_utils.py` + `packages/vig-utils/tests`. Every dependency-light test file added recently runs only on developer machines, never in CI:

- `tests/test_transforms.py` (#1036 — incl. the manifest/banner invariants)
- `tests/test_workflow_sync_checkout.py` (#1034)
- `tests/test_workflow_private_repo_guard.py` (#1039)
- `tests/test_release_tag_prefix.py`, `tests/test_floating_tags.py`, `tests/test_scaffold_downstream_release_doc.py` (#1044/#1045/#1046)
- `tests/test_workflow_pr_agent_fingerprints.py` (#1052)
- `tests/test_scaffold_lint.py` (#1056/#1057, in flight)

First observed consequence: the DOWNSTREAM_RELEASE identity test silently went red on dev (companion issue). The heavier suites (flake/image/install) are deliberately targeted elsewhere in ci.yml — this is only about the cheap, no-nix, no-image shape tests.

## Fix

Include the lightweight suites in the Project Checks pytest run. Prefer a future-proof selection over another hand-list that goes stale — e.g. run `tests/` with explicit deselection of the heavy modules (they are a known, slow-changing set), or a pytest marker convention (`-m "not heavy"`), whichever fits the repo's existing conventions with the smallest diff. New shape-test files must run in CI by default, with no action-file edit required.

Refs: #1034, #1036, #1051
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:29 PM_

Fixed in #1065 (merged to dev): Project Checks now runs tests/ minus an explicit deny-list of the 9 heavy modules (each covered by its dedicated targeted CI job). New shape-test files run in CI automatically — verified live twice as #1063's and #1064's test files were swept in with no action edits (640 → 678 tests, ~10s).

