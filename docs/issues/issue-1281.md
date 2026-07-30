---
type: issue
state: closed
created: 2026-07-28T13:26:56Z
updated: 2026-07-29T13:07:51Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1281
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-30T05:15:36.151Z
---

# [Issue 1281]: [fix(workspace): just test fails on Python repos with zero collected tests (pytest exit 5)](https://github.com/vig-os/devkit/issues/1281)

### Description

The scaffolded `justfile.project` gates the `test` and `test-cov` recipes on `pyproject.toml` presence:

```just
test *args:
    @if [ -f pyproject.toml ]; then uv run pytest {{ args }}; fi
```

A consumer that **has** a `pyproject.toml` but **no test suite** (data repos, config-only repos, freshly scaffolded projects before the first test lands) gets `uv run pytest` → exit code 5 ("no tests collected") → a red `just test`, and a red CI `test` job out of the box.

### Steps to Reproduce

1. Repo with a `pyproject.toml` and zero collected tests
2. `just test`

### Expected Behavior

A no-op success — "nothing to test" is not a failure, matching how non-Python consumers (no `pyproject.toml`) silently no-op through the same recipe.

### Actual Behavior

pytest exits 5, the recipe fails under `set shell := bash -euo pipefail`, and CI's `test` job goes red on a repo with no defect.

### Environment

devkit 1.4.2, scaffolded `justfile.project` (`test`, `test-cov` recipes), `ci.yml` `test` job (`just test`).

### Possible Solution

Treat exit code 5 as success in both recipes, e.g. `uv run pytest {{ args }} || test $? -eq 5` (mind `-euo pipefail` semantics), or additionally gate on a `tests/` directory existing. Cover with a smoke/bats case. Related context: #944 (pytest packaging in the `#python` template also broke `just test`).

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on July 29, 2026 at 01:07 PM_

Merged to dev via #1290 (dev-targeted PRs do not auto-close). Ships with the next release.

