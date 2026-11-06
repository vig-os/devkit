---
type: issue
state: open
created: 2026-11-06T03:29:46Z
updated: 2026-11-06T03:29:46Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2057
comments: 0
labels: area:workflow, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T09:11:24.679Z
---

# [Issue 2057]: [Harden the container-job git-before-safe.directory guard (#2055) against bypass spellings](https://github.com/vig-os/devkit/issues/2057)

Found in review of #2056. The guard `test_container_job_runs_no_git_before_safe_directory` passes today, but it does not catch these spellings of a git call in a step before the safe.directory setup:

- `/usr/bin/git rev-parse HEAD`: a path prefix before `git`
- `GIT=git; $GIT status`
- `bash -c 'git status'`: a quote directly before `git`
- `gh pr view …`: gh shells out to git to resolve the repo
- `echo safe.directory; git status`: any `run:` that merely contains the string `safe.directory` is taken as the setup step
- `uses:` steps before setup, e.g. a composite action that calls git, are not scanned at all

**Acceptance:**
- Allow `/` and quote characters before `git` in the detector, and match `gh`.
- Identify the setup step by the actual `git config … safe.directory` command (or the setup-devkit-toolchain step id), not by a substring.
- Resolve local composite actions one level deep.
- Add a fixture test for each spelling above.

Not blocking: no current workflow does any of these.
