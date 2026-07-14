---
type: issue
state: open
created: 2026-07-14T16:51:00Z
updated: 2026-07-14T16:51:00Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1074
comments: 0
labels: bug, priority:medium, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:22.612Z
---

# [Issue 1074]: [fix(vigutils): validate-commit-range title check treats all types as Refs-optional](https://github.com/vig-os/devkit/issues/1074)

Found during review of release PR #1068.

`validate_title` passes `refs_optional_types=approved_types`, making **every** commit type Refs-optional for titles. As a result a string like `docs: update readme` passes as a title but the same string fails as a full commit message (`docs` is not in `DEFAULT_REFS_OPTIONAL_TYPES`).

Since a `--no-ff` merge commit's subject is that title, we should confirm the merge-commit path is exempt from `validate-commit-msg` downstream — otherwise a merge could pass title validation but fail commit validation on `dev`.

**Action:** confirm/document the merge-commit exemption, or align the two Refs-optional sets.

**File:** `packages/vig-utils/src/vig_utils/validate_commit_range.py:117`

