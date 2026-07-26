---
type: issue
state: closed
created: 2026-07-21T08:29:59Z
updated: 2026-07-21T11:59:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1235
comments: 1
labels: chore, area:workspace
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:39.590Z
---

# [Issue 1235]: [install.sh --docker: chown scaffold output before the host-side git phase](https://github.com/vig-os/devkit/issues/1235)

## Problem

Under `--docker`, the scaffold output is written root-owned via the bind mount. `install.sh`'s host-side git phase (`setup_git_repo`, wrapped warn-not-fail around `install.sh:946`) then runs against the still-root-owned tree and fails with `.git: Permission denied` — by design only a warning, so the installer "succeeds" but leaves a root-owned tree with no git repo. Every `--docker` caller on a hosted runner must then repair ownership and `git init` by hand; the direnv smoke lane (devkit-smoke-test#286, #1194) carries exactly that workaround (unconditional `chown` + post-hoc `git init`).

The warn-not-fail posture of the git phase is deliberate (CI/fresh-machine friendliness) and should stay.

## Suggested fix

In the `--docker` path, chown the scaffold output back to the invoking user **before** the git phase runs, so `setup_git_repo` succeeds normally and downstream workarounds become unnecessary. Then simplify the direnv smoke lane's workaround in `assets/smoke-test/.github/workflows/direnv-smoke.yml` (and devkit-smoke-test) once released.

Found during review of the #1194 lane (both failed iterations of devkit-smoke-test#286 root-caused to this). Low priority — everything works today with the workaround in place.

Refs: #1194
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:59 AM_

Fixed on dev via PR #1245 (merge commit 53b637e4): on the docker runtime only, a throwaway container chowns /workspace to the invoking uid:gid after the scaffold run and before setup_git_repo; rootless podman is skipped (already uid-mapped). Covered by bats tests incl. ordering. The smoke-lane manual chown workaround can be simplified once this releases. Ships with 1.4.1.

