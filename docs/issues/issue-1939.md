---
type: issue
state: open
created: 2026-10-27T09:09:08Z
updated: 2026-10-27T09:09:08Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1939
comments: 0
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:58.446Z
---

# [Issue 1939]: [Flaky scaffold-drift test: detached git maintenance repacks fixture objects during the drift step's local clone](https://github.com/vig-os/devkit/issues/1939)

**Symptom:** `tests/test_scaffold_drift.py::test_nix_drift_reports_clean_then_drift[False]` fails intermittently in CI: `git clone` exits 128 with `failed to copy .git/objects/7c/23ee…: No such file or directory` (PR #1937, run on head c7ce9f94). The same object-copy failure was seen locally on 2026-10-26 while working on #1907.

**Root cause** (the same mechanism as #1815): the test makes commits in its fixture repo (`ws`), and each `git commit` spawns a detached `git maintenance run --auto` that can repack and delete loose objects. The drift step under test then runs `git clone --quiet "$GITHUB_WORKSPACE" "$scratch/workspace"` (a local clone, which copies or hardlinks loose objects one by one) while that maintenance is still running. The clone loses the race. `tests/conftest.py::scaffold_files` already documents this for tree walks, but the drift test's clone path is unprotected.

**Fix:** turn off auto-maintenance in the test's own fixture repos. Add `-c maintenance.auto=false -c gc.auto=0` to the shared `git` argv in the test, or set both keys in the fixture repo's config right after `git init`. Apply it everywhere in tests/ that commits in a fixture repo and then clones, copies, or walks `.git` (grep for `git init` in tests/). Ideally there is one shared helper in conftest.py, so there is a single source of truth. Don't add retries or sleeps.

**Acceptance:** a regression test that fails without the fix. For example, commit in a fixture repo and assert that the repo's effective `maintenance.auto` is `false` (`git config --get`), or deterministically start maintenance before the clone. CI green.

