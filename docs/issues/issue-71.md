---
type: issue
state: open
created: 2026-02-18T01:46:51Z
updated: 2026-06-23T06:56:46Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/71
comments: 5
labels: feature, priority:medium, area:workspace, effort:large, semver:minor
assignees: gerchowl
milestone: 0.4
projects: none
parent: none
children: 73, 66
synced: 2026-06-23T08:02:58.673Z
---

# [Issue 71]: [[FEATURE] Expand justfile.base with devcontainer, quality, security, docs, info, and git recipes](https://github.com/vig-os/devcontainer/issues/71)

### Description

Expand `assets/workspace/.devcontainer/justfile.base` with ~18 new recipes covering devcontainer lifecycle, code quality, security scanning, documentation, environment info, git helpers, and release utilities. Also add commented-out stubs to `assets/workspace/justfile.project` for opinionated recipes teams can customize.

### Problem Statement

The current `justfile.base` ships only 9 recipes (lint, format, precommit, test-pytest, test-cov, sync, update, clean-artifacts, sidecars/sidecar). Developers in downstream projects must manually run docker compose commands to start/stop the devcontainer, have no local CI mirror, no security scanning shortcuts, and no quick environment diagnostics. This leads to inconsistent workflows and repeated boilerplate across projects.

### Proposed Solution

Add the following recipes to `justfile.base` (managed by devcontainer, replaced on upgrade):

**devcontainer group (7 recipes):**
- `up` — start devcontainer + sidecars via compose (auto-detect podman/docker)
- `open` — open Cursor/VS Code attached to the running container
- `down` — stop and remove containers
- `status` — show container status
- `logs *args` — tail container logs
- `shell` — open bash in running container
- `restart *args` — restart service(s)

**quality group (2 new recipes, extending existing):**
- `check` — run lint + format-check + test-pytest (local CI mirror)
- `format-check` — verify formatting without changing files

**security group (2 recipes):**
- `audit` — dependency vulnerability scan via pip-audit
- `scan` — static security analysis via bandit

**docs group (2 recipes):**
- `docs` — live-preview documentation via mkdocs serve
- `docs-build` — build docs with strict mode (for CI validation)

**info group (3 recipes):**
- `env-info` — print Python/uv/OS versions and key env vars
- `outdated` — show stale dependencies
- `version` — print current project version from pyproject.toml

**git group (2 recipes):**
- `log` — pretty one-line git log (last 20 commits)
- `branch` — show current branch + list recent branches

**release group (1 recipe):**
- `changelog` — print the Unreleased section of CHANGELOG.md

**justfile.project stubs (commented-out):**
- `run`, `serve`, `migrate`, `seed`, `docs-deploy`

Container runtime auto-detection: try `podman compose` first, fall back to `docker compose`.

### Alternatives Considered

- **Keep justfile.base minimal**: Let each project add its own recipes. Downside: duplicated boilerplate, inconsistent UX across projects.
- **Ship a large opinionated justfile.base**: Include framework-specific recipes (FastAPI, alembic, etc.). Downside: not universal — would break for non-matching projects.
- **Chosen approach**: Universal recipes in `justfile.base` + commented-out stubs in `justfile.project` for opinionated patterns.

### Impact

- Benefits all downstream projects using the vigOS devcontainer
- Backward compatible — adds new recipes, does not modify existing ones
- Recipes that depend on optional tools (mkdocs, pip-audit, bandit) fail gracefully if the tool is not installed

### Changelog Category

Added
---

# [Comment #1]() by [gerchowl]()

_Posted on February 21, 2026 at 11:48 PM_

## Implementation Plan

Issue: #71
Branch: `feature/71-expand-justfile-base-recipes`
Scope: Devcontainer lifecycle (7 host-side recipes) + Git helpers (2 recipes). All other groups deferred per YAGNI.

### Tasks

- [ ] Task 1: Add compose detection variable and host-only guard — `assets/workspace/.devcontainer/justfile.base` — verify: `just --list` shows no errors
- [ ] Task 2: Add `up` recipe (start devcontainer + sidecars via compose) — `assets/workspace/.devcontainer/justfile.base` — verify: `just --list | grep up`
- [ ] Task 3: Add `down` recipe (stop and remove containers) — same file — verify: `just --list | grep down`
- [ ] Task 4: Add `status` recipe (show container status) — same file — verify: `just --list | grep status`
- [ ] Task 5: Add `logs` recipe (tail container logs) — same file — verify: `just --list | grep logs`
- [ ] Task 6: Add `shell` recipe (open bash in running container) — same file — verify: `just --list | grep shell`
- [ ] Task 7: Add `restart` recipe (restart services) — same file — verify: `just --list | grep restart`
- [ ] Task 8: Add `open` recipe (open Cursor/VS Code attached to container) — same file — verify: `just --list | grep open`
- [ ] Task 9: Add `log` recipe (pretty one-line git log) — same file — verify: `just --list | grep log`
- [ ] Task 10: Add `branch` recipe (current branch + recent branches) — same file — verify: `just --list | grep branch`
- [ ] Task 11: Update CHANGELOG.md — `CHANGELOG.md` — verify: grep Unreleased section has new entries

### Notes

- TDD skipped: justfile recipes are config/templates, not testable code.
- All devcontainer recipes use a host-only guard (exit if running inside container).
- Compose command auto-detected: `podman compose` preferred, fallback to `docker compose`.
- Tasks 1–8 can be batched into a single commit (devcontainer group).
- Tasks 9–10 can be a second commit (git group).
- Task 11 is a separate changelog commit.

---

# [Comment #2]() by [gerchowl]()

_Posted on February 21, 2026 at 11:58 PM_

## Autonomous Run Complete

- Design: posted (scoped plan in comments)
- Plan: posted (11 tasks)
- Execute: all tasks done
- Verify: all checks pass
- PR: https://github.com/vig-os/devcontainer/pull/151
- CI: all checks pass

---

# [Comment #3]() by [gerchowl]()

_Posted on February 22, 2026 at 09:22 AM_

## Implementation Plan (SSoT Refactor)

**Why this change:** The first implementation edited `assets/workspace/.devcontainer/justfile.base` directly, leaving root `justfile.base` minimal. That created two separate sources of truth: root had fewer recipes than the workspace template, and sync never touched justfile.base. Developers working on the devcontainer repo itself missed useful recipes (log, branch, etc.), and any future edits required manual sync between the two files. This refactor makes root `justfile.base` the canonical source and adds it to the sync manifest, so there is one source of truth and `just sync-workspace` / prepare-build keep the workspace template in sync.

---

Issue: #71
Branch: `feature/71-expand-justfile-base-recipes`
Scope: Make root `justfile.base` the canonical source and sync it into the workspace template via the manifest.

### Context

- Root `justfile.base` is minimal; `assets/workspace/.devcontainer/justfile.base` has the full recipes (devcontainer, git, check, devcontainer-upgrade).
- Both are maintained separately; `justfile.base` is not in the sync manifest.
- Goal: single source of truth at repo root, synced to workspace template.

### Tasks

- [ ] Task 1: Replace root `justfile.base` with full content from `assets/workspace/.devcontainer/justfile.base` — `justfile.base` — verify: `just --list` shows all recipes (devcontainer, git, check, etc.)
- [ ] Task 2: Add manifest entry for `justfile.base` — `scripts/sync_manifest.py` — add `Entry(src="justfile.base", dest=".devcontainer/justfile.base")` next to justfile.gh/justfile.worktree — verify: `just sync-workspace` runs; `uv run python scripts/sync_manifest.py list` shows entry
- [ ] Task 3: Run sync and confirm no diff — `just sync-workspace` — verify: `git diff assets/workspace/.devcontainer/justfile.base` is empty
- [ ] Task 4: Update CHANGELOG.md — add entry under Unreleased that justfile.base is now canonical and synced via manifest — verify: `grep -A2 justfile.base CHANGELOG.md`

### Notes

- TDD skipped: manifest/config change only.
- Devcontainer recipes (up, down, check) assume `.devcontainer/` exists; they may fail when run from devcontainer repo root. Git recipes (log, branch) work from any directory.

---

# [Comment #4]() by [gerchowl]()

_Posted on February 22, 2026 at 09:33 AM_

## Autonomous Run Complete (SSoT Refactor)

- Execute: all 4 tasks done
- Verify: lint passed
- PR: https://github.com/vig-os/devcontainer/pull/151 (updated with new commit)
- CI: most checks pass; Security Scan still pending

---

# [Comment #5]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Coordinate with #625: the scaffolded modes (#641) should expose a consistent recipe set so direnv-only repos still get the relevant `justfile.base` recipes.

