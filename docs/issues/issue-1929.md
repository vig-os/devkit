---
type: issue
state: open
created: 2026-10-27T08:54:37Z
updated: 2026-10-27T08:54:37Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1929
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:02.483Z
---

# [Issue 1929]: [#1908 S3: `devkit-upgrade` migration](https://github.com/vig-os/devkit/issues/1929)

Implementation sub-issue **S3** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* §6. It ships in release N and **acts from the migrating adoption**
  (§6):
  - N's `devkit-upgrade.yml` passes `vars.CI_RUNNER_*` into the install step
    and lifts the `ci-runner-migration:` lines into a "CI runner migration"
    PR-body section;
  - `init-workspace.sh` handles the legacy key per (c), keeps it when no
    variables are visible (which is always the case in the adoption of N),
    prints the lines, and adds the private no-variables hint row;
  - the seeded-hook reconcile per (d).
- *Files:* `assets/init-workspace.sh` (the legacy-key migration in the
  persistence block, rebased on S1b's lane-size lines there), `assets/workspace/.github/workflows/devkit-upgrade.yml` (the
  install and PR-body steps; S2 touches only `runs-on`),
  `tests/bats/init-workspace.bats` (migration cases), and the devkit-upgrade
  workflow tests.
- *Acceptance:*
  - bats cases for every row of the §6 table;
  - the strip/keep outcome per (c);
  - with no `CI_RUNNER_*` in the environment (the pre-N workflow), the key is
    always kept;
  - **the "adopt N+1 before releasing N to main" path:** run N+1's
    `init-workspace.sh` with the pre-N workflow's environment (no
    `CI_RUNNER_*`). The key is kept, and the `ci-runner-migration:` lines are
    printed but not lifted, because the pre-N workflow's PR-body step is
    unchanged. A companion S9 test then asserts that at N+2 that repo is green
    with a warning when its variables cover every required class, and red
    with the full text when they do not;
  - the reconcile/drift lines per (d);
  - a workflow test that the install step's `env` carries all three
    variables and that the PR-body step lifts the lines.

Refs #1908
