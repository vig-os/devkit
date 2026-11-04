---
type: issue
state: open
created: 2026-11-04T02:01:03Z
updated: 2026-11-04T02:01:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2021
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:30.525Z
---

# [Issue 2021]: [test_dry_run_creates_no_files flakes on a 10 s subprocess timeout](https://github.com/vig-os/devkit/issues/2021)

`tests/test_utils.py::TestInstallScriptUnit::test_dry_run_creates_no_files` failed in CI run 41754980457 (PR #2017) with `subprocess.TimeoutExpired` for `install.sh --dry-run` after 10 seconds. That run had 3789 passed and 1 failed. A re-run of the same head passed.

The PR did not touch `install.sh` or `tests/test_utils.py`; both are identical to dev.

Find out what `install.sh --dry-run` waits on under a loaded runner: network, nix, or a slow probe. Either make the dry run not depend on it, or give the test a timeout justified by measured runtimes. Do not paper over it with a blind retry.

Refs: #2017
