---
type: issue
state: open
created: 2026-10-27T08:54:33Z
updated: 2026-10-27T08:54:33Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1927
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:03.449Z
---

# [Issue 1927]: [#1908 S1b: Per-lane size override `DEVKIT_CI_LANE_SIZES`](https://github.com/vig-os/devkit/issues/1927)

Implementation sub-issue **S1b** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:*
  - parse `DEVKIT_CI_LANE_SIZES` in `resolve-toolchain`, with an `::error::`
    on an unknown lane or size;
  - the init-workspace write-path guard and persistence;
  - the template comment;
  - each class an override names joining the required classes (LARGE or
    XLARGE), and no other class being required.
- *Files:* `resolve-toolchain/action.yml` (its parser section),
  `assets/init-workspace.sh` (guard and persistence),
  `assets/workspace/.vig-os` (the key and its comment), and the lane-size
  cases in `tests/test_ci_runner.py` and `tests/bats/init-workspace.bats`, and
  `DEVKIT_CI_LANE_SIZES` added to `MANIFEST_KEYS` in
  `tests/test_vig_os_manifest.py`.
- *Acceptance:*
  - an override moves a lane's `runners` entry;
  - invalid values fail at both the write path and resolve;
  - persisted across `--force`;
  - the default map puts every lane on `small`;
  - an override to LARGE or XLARGE with that class unset keeps the lane on
    the hosted default and gives the §3 `::warning::` naming the variable and
    the lane (the diagnostic itself is tested in S1d);
  - a set LARGE or XLARGE that no lane uses gives no notice and is not
    required.

Refs #1908
