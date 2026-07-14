---
type: issue
state: closed
created: 2026-07-14T11:46:45Z
updated: 2026-07-14T12:29:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1060
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:25.014Z
---

# [Issue 1060]: [[BUG] test_scaffold_doc_matches_root_sssot fails on dev — byte-identity assertion is banner-unaware](https://github.com/vig-os/devkit/issues/1060)

## Problem

`tests/test_scaffold_downstream_release_doc.py::test_scaffold_doc_matches_root_sssot` (added in #1051) asserts byte-identity between the root `docs/DOWNSTREAM_RELEASE.md` SSoT and the scaffold copy. #1043's provenance banner stamps a 3-line HTML-comment banner on the scaffold copy, so the assertion has failed on dev since the #1043 merge (verified locally on current dev tip: 1 failed, 2 passed).

Same lesson as the `is_transformed` fix inside #1043: identity assertions over manifest-synced files must be banner-aware.

## Why CI didn't catch it

The test file never runs in CI — see the companion issue about the Project Checks pytest scope. The two bugs compound: an unrun test that silently went red.

## Fix

Make the comparison banner-aware: strip the banner block (reuse/expose the Banner transform's own strip helper from `scripts/transforms.py` — do not re-implement the banner shape) from the scaffold copy before comparing, so the assertion still guards real content drift.

Refs: #1051, #1043, #1036
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:29 PM_

Fixed in #1065 (merged to dev): the identity assertion strips the banner via the new transforms.strip_banner() — the Banner transform's own inverse, not a re-encoded shape — and still guards real content drift.

