---
type: issue
state: open
created: 2026-10-27T09:24:14Z
updated: 2026-10-27T09:24:14Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1942
comments: 0
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:58.062Z
---

# [Issue 1942]: [Test isolation: install-direnv-host leftover check reads the shared TMPDIR, so it flakes under pytest -n](https://github.com/vig-os/devkit/issues/1942)

**Symptom:** under `pytest -n N` (local runs; CI runs serially), `tests/test_install_direnv_host.py` (~L170) intermittently fails its assertion that `$TMPDIR` holds no `devkit-scaffold.*` directories.

**Root cause:** `install.sh` (~L852) creates `mktemp -d "$TMPDIR/devkit-scaffold.XXXXXX"`. The test checks the *shared* `$TMPDIR` for leftovers, so any parallel worker that is running `install.sh` at that moment trips the assertion. This is test isolation, not a leak in install.sh. Found while reviewing #1941 (#1939).

**Fix:** give each such test its own `TMPDIR` (e.g. `monkeypatch.setenv("TMPDIR", tmp_path / "tmp")` passed into the subprocess env) and assert leftovers only there. Don't add retries.

**Acceptance:** run the file with `-n 4` several times with no failures, and the assertion still catches a deliberately leaked `devkit-scaffold.*` directory in the test's own TMPDIR.

