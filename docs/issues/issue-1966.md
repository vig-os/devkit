---
type: issue
state: open
created: 2026-10-29T09:17:53Z
updated: 2026-10-29T09:17:54Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1966
comments: 0
labels: chore, area:testing
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:26.595Z
---

# [Issue 1966]: [consumer-matrix: follow-ups from S8 final review](https://github.com/vig-os/devkit/issues/1966)

Follow-ups from the final review of PR #1958 (S8 #1935). There are no blockers. The gaps that matter are already caught by other tests, but the matrix itself should prove them.

1. **Hand-typed upgrade env.** `migrating_adoption` (render-cell.sh) hand-types the N `devkit-upgrade.yml` upgrade-step env (`DEVKIT_UPGRADE_CONTEXT=1`, `..._CI_RUNNER_*`) and calls install.sh directly. Mutating N's real workflow leaves the matrix green; only `test_workflow_devkit_upgrade.py::test_runner_migration_environment_and_pr_channel` catches it. Replay N's real upgrade step through `tests/workflow_replay.py` instead.
2. **Split bats test 30.** Make `HOOK_DRIFT` alone go red (for example by setting it to a migration-like line). Today the `BASE` edit masks it.
3. **Target version.** It comes from the devkit repo's root `.vig-os` `DEVKIT_VERSION` pin (1.18.0), not from the version under test. It's only a label, because the adapters serve the checkout, but it's misleading. Derive it from the version under test, or rename it.
4. **Inconsistent name.** `CONSUMER_MATRIX_RUNNER_LABEL` doesn't match the `_LARGE`/`_XLARGE` names next to it.
5. **Redundant config.** `prepare_adoption` sets the git identity config, and `fixture_commit` passes the same `-c` flags again. Remove one.
6. **Hardcoded fixture value.** `runners()` hardcodes the `pool-legacy` fixture value; derive it from the cell's fixture.

Refs: #1935
