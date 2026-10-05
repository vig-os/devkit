---
type: issue
state: closed
created: 2026-10-05T06:42:47Z
updated: 2026-10-05T07:30:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1815
comments: 2
labels: bug, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-05T08:48:20.995Z
---

# [Issue 1815]: [Placeholder-scan tests race against git housekeeping in .git/objects](https://github.com/vig-os/devkit/issues/1815)

### Description

The placeholder-scan tests walk the whole scaffolded workspace with a lazy `rglob("*")`, `.git/` included, and `read_text()` every file. A loose git object listed by the walk can be gone by the time it is opened, crashing the test with `FileNotFoundError` (only `UnicodeDecodeError` is caught).

Seen once on PR #1812 (run 37247340361, job Integration Tests, 89 passed / 1 failed); passed on re-run:

```
tests/test_install_script.py::TestInstallScriptIntegration::test_install_replaces_org_name_placeholder
FileNotFoundError: [Errno 2] No such file or directory: '.../tests/tmp/Install-Test-Project-k8aucshk/.git/objects/c5/1db2915d65b7336def5d6d0558455933cd8eef'
```

Probable (unverified) mechanism: `install.sh` runs `git add -A && git commit` on the host, and git's detached auto-maintenance packs/prunes loose objects while the test is walking.

Scanning `.git/objects` is meaningless anyway: objects are zlib-compressed and can never contain a placeholder.

### Steps to Reproduce

Nondeterministic. Run the Integration Tests CI job; rare.

### Expected Behavior

Placeholder scans only cover scaffolded files and are immune to concurrent git housekeeping.

### Actual Behavior

Intermittent `FileNotFoundError` on a `.git/objects/` path fails Integration Tests.

### Possible Solution

- `tests/test_install_script.py:199` (`test_install_replaces_placeholder`) and `:234` (`test_install_replaces_org_name_placeholder`): skip paths under `.git/`, materialize the file list before reading.
- `:234` duplicates the parametrized `{{ORG_NAME}}` case at `:199` — consider removing it.
- `tests/test_integration.py:590` (`test_placeholders_replaced`): same lazy-walk pattern; add `.git` to `excluded_paths`.

Test-only change; TDD red phase not applicable (nondeterministic race).

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on October 5, 2026 at 06:52 AM_

## Root cause analysis

**The deleter is git's own background auto-maintenance, triggered by the scaffold commit in `install.sh`.**

1. `install.sh` (`setup_git_repo`) runs `git commit` for the initial scaffold. Every `git commit` spawns `git maintenance run --auto --quiet --detach` (confirmed with `GIT_TRACE` on git 2.55.0, the version on the `ubuntu-26.04` runner).
2. Since git 2.54 the default maintenance strategy is `geometric` (2.54.0 release notes). Its `geometric-repack` task fires at `maintenance.geometric-repack.auto` = 100 loose objects. Like `gc --auto`, the auto check estimates the count by sampling `.git/objects/17/` × 256. So 1 object in that bucket means "not needed", and 2 or more means "repack".
3. A fresh scaffold commit leaves ~161 loose objects. Whether two of them land in `17/` depends on content. The commit object's hash embeds a timestamp, so it varies per run, which is why the failure is rare.
4. When the repack triggers, it packs every loose object and deletes all the loose files ~200–400 ms after the commit. The class fixture returns right after `install.sh`, and the placeholder walks are the first tests in the class. A lazy `rglob("*")` that walks into `.git/objects/` can therefore list a file that is gone by the time `read_text()` opens it, which raises `FileNotFoundError`.

### Evidence

- Local `install.sh` run, then the scaffold commit replayed with git 2.55.0 and a minimal config:
  - `GIT_TRACE` shows `git maintenance run --auto --quiet --detach` started by `commit`.
  - Scaffold as-is (1 object in `objects/17/`): `maintenance is-needed --auto` says not needed, and the 161 loose objects stay put.
  - The same scaffold plus one extra file whose blob hashes into `17/`: **162 loose / 0 packs → 0 loose / 1 pack within 400 ms** of the commit.
- The vanished object `c51db29…` is an ordinary scaffold blob (`.devcontainer/scripts/copy-host-user-conf.sh`). It existed after the commit and was removed by the repack.
- The apparent 10.5 s runtime of the failed test is an artifact. `-x` runs the session devcontainer teardown (`podman rm -f`) before the FAILED line is printed. The walk itself takes ~15 ms, the same as the three walks just before it.

### Ruled out

- Background processes from `install.sh` or the devcontainer lifecycle scripts: there are none.
- The session devcontainer's `tests/` bind mount: nothing in the container touches `tests/tmp`.
- Parallel pytest: the job runs serially.

### Impact

Tests only. The background repack is correct and desirable in a real consumer repo, so `install.sh` is unchanged.

## Fix

- One shared test helper returns the scaffold's regular files as a materialized, sorted list, excluding `.git/`. Git internals can never contain a placeholder.
- The helper is used by `test_install_replaces_placeholder` (`tests/test_install_script.py`) and `test_placeholders_replaced` (`tests/test_integration.py`). The integration workspace is also a git repo with commits, so it is exposed to the same race.
- `test_install_replaces_org_name_placeholder` is deleted. It duplicates the parametrized `{{ORG_NAME}}` case.
- Not done: disabling maintenance in the fixtures. Excluding `.git` removes the race, and fixtures should keep real-install behaviour.


---

# [Comment #2]() by [c-vigo]()

_Posted on October 5, 2026 at 07:30 AM_

Fixed by #1816 (merged to `dev` as 3aa23c62); reaches `main` with the next release train.

