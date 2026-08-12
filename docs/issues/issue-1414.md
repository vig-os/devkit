---
type: issue
state: closed
created: 2026-08-11T08:17:20Z
updated: 2026-08-11T08:58:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1414
comments: 1
labels: bug, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:07.538Z
---

# [Issue 1414]: [Scaffold ci.yml summary gate does not fail on cancelled required checks](https://github.com/vig-os/devkit/issues/1414)

## Description

The devkit `ci.yml` summary gate treats a **cancelled** required check as a failure (per the #1371 doctrine: cancelled must trip the gate), but the scaffolded consumer copy (`assets/workspace/.github/workflows/ci.yml`) implements the cancelled leg **only** for the resolve-toolchain check. For the other required checks (lint, test, commit-checks, scaffold-drift, dependency-review) a cancelled run does not trip the consumer summary gate, so a consumer PR whose required job was cancelled can still show a green summary.

Surfaced while consolidating the workflow-shape tests in #1413: the summary-gate test could not be parametrized over both `ci.yml` copies because the doctrine assertion fails on the scaffold copy.

## Expected behavior

Scaffold `ci.yml` summary job mirrors the devkit copy: cancelled results trip the gate for every required check, and `tests/test_workflow_summary_gate.py` is parametrized over both copies to pin the parity.

## Steps to reproduce

Compare the summary job's result checks in `.github/workflows/ci.yml` vs `assets/workspace/.github/workflows/ci.yml`; only the former handles `cancelled` for all required checks.

Refs: #1371, #1413

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 08:58 AM_

Fixed in PR #1416 (merged to dev @d7a5afdc): the scaffolded ci.yml summary gate now trips on cancelled results for every needed job (lint, test, commit-checks, scaffold-drift, dependency-review — resolve-toolchain already had it), matching the devkit copy's #1371 doctrine. Pinned by tests/test_workflow_summary_gate.py, now parametrized over both copies (written red-first against the scaffold). Ships to consumers with the next devkit release.

