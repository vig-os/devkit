---
type: issue
state: open
created: 2026-11-08T10:12:44Z
updated: 2026-11-08T10:12:44Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2064
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-09T09:33:49.754Z
---

# [Issue 2064]: [ci: Commit Messages gate re-validates main's commits on a main→dev sync PR (no --exclude-reachable origin/main)](https://github.com/vig-os/devkit/issues/2064)

## Problem
In the generated `ci.yml`, the `Commit Messages` job excludes `origin/dev`-reachable commits only when the PR base is not `dev` (release PRs into main, #1149). A **sync PR main → dev** (merging `main` back into `dev` after a release, or after hotfixes merged straight into main) therefore re-validates commits that are **already on main**, against the current validator. Older commits that were valid when they landed now fail the gate. For example, the newer "single trailing Refs line" rule rejects them.

Seen on gerchowl/claude-config PR #178 (2026-11-08): `validate-commit-range` rejects main's squash commits c4e4f6fd, 0065e08e, f27d2627 and 2000485a. This blocks the 0.5.0 release train, because a release PR from dev would conflict, and GitHub runs no `pull_request` CI on a conflicting PR.

## Proposed fix
Mirror the existing rule: commits already reachable from the release branch were gated (or grandfathered) when they landed. So on a PR whose base IS the trunk (`dev`), also exclude `origin/main`:

```bash
EXCLUDE=()
TRUNK="dev"; RELEASE="main"
if [ "${BASE_REF}" != "${TRUNK}" ] && git fetch --no-tags --quiet origin "${TRUNK}" 2>/dev/null; then
  EXCLUDE+=(--exclude-reachable "origin/${TRUNK}")
elif [ "${BASE_REF}" = "${TRUNK}" ] && git fetch --no-tags --quiet origin "${RELEASE}" 2>/dev/null; then
  EXCLUDE+=(--exclude-reachable "origin/${RELEASE}")
fi
```

This is a no-op on normal feature PRs into dev: they contain no main-only commits, and their own commits are still validated.

