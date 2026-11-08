---
type: issue
state: open
created: 2026-10-27T08:54:48Z
updated: 2026-10-27T08:54:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1935
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:59.197Z
---

# [Issue 1935]: [#1908 S8: Release N gate](https://github.com/vig-os/devkit/issues/1935)

Implementation sub-issue **S8** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* verify S1–S7b on the consumer matrix and in one self-hosted consumer
  before cutting N, including a **gitflow consumer whose `dev` is ahead of
  `main`**. Its N adoption runs the pre-N workflow from `main`; the matrix
  checks that the key is kept and that the per-run warning carries the full
  migration text on the `dev` PR.
- *Files:* `scripts/consumer-matrix/render-cell.sh` and
  `tests/bats/consumer-matrix.bats`. The self-hosted cell seeds variables
  instead of the key.
- *Acceptance:*
  - the matrix is green with the key only (the warning path) and with
    variables only;
  - in the gitflow cell, the adoption PR's CI log has the full-text warning,
    and the pre-N PR body has no migration section, which is expected.

Refs #1908
