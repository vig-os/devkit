---
type: issue
state: closed
created: 2026-08-11T07:23:05Z
updated: 2026-08-11T07:34:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1411
comments: 1
labels: docs
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:08.695Z
---

# [Issue 1411]: [[DOCS] Refresh CLAUDE.md (repo name, command table, release-operations pointers) and add the green-CI dispatch rule to RELEASE_CYCLE.md](https://github.com/vig-os/devkit/issues/1411)

### Description

`CLAUDE.md` predates the last three release trains (last touched at the 1.4.0 workflow-model change) and has drifted:

1. **Stale title**: "Project: vigOS Devcontainer" — the repo is `vig-os/devkit`. Stale pre-rename names have already caused a real bug (#1396).
2. **Command table drift**: `/solve-and-pr` exists in `.claude/skills/` but is missing from the table.
3. **No release-operations layer**: the file is silent on the repo's dominant recurring activity. Agents and contributors have to rediscover the doc set (`RELEASE_CYCLE.md`, `CROSS_REPO_RELEASE_GATE.md`, `DOWNSTREAM_RELEASE.md`, `SOLO_ADOPTION.md`, `MIGRATION.md`, `WORKFLOW_SECURITY.md`) every session, and recent paradigm changes (deferred-approval model, smoke human-approval gate, automated consumer adoption via devkit-upgrade — no more consumer-lane dispatch) have no entry point. Per the file's own SSoT rule this should be a lean pointer section, not copied content.
4. **A hard operational rule is missing from the repo entirely**: never dispatch `release.yml` (candidate or final) until the release-branch PR CI is fully green — the draft PR opening is not the go-signal. This mistake has recurred across trains and `RELEASE_CYCLE.md` does not state it; it belongs in Phase 2 where candidates are cut.

### Documentation Type

Update existing documentation

### Target Files

- https://github.com/vig-os/devkit/blob/main/CLAUDE.md
- https://github.com/vig-os/devkit/blob/main/docs/RELEASE_CYCLE.md

### Related Code Changes

Follows the same review as #1409. Repo-rename context: #1396. Adoption paradigm: #1404/#1405. Full `vig-os/devcontainer` → `devkit` naming sweep across docs stays a separate issue (noted in #1409).

### Acceptance Criteria

- [ ] `CLAUDE.md` title names the repo correctly (`vig-os/devkit`)
- [ ] `/solve-and-pr` listed in the command table
- [ ] New lean "Release Operations" section: pointers to the release doc set plus the few agent-behavioral hard rules (green-CI-before-dispatch, immutable-release forward-fix, adoption is automated — no consumer-lane dispatch)
- [ ] `RELEASE_CYCLE.md` Phase 2 states the green-CI-before-dispatch rule where candidates are cut
- [ ] No content copied down a level — `CLAUDE.md` links, docs remain SSoT

### Changelog Category

Changed

### Additional Context

Prompted by a maintainer review of agent-facing docs after the 1.7.0 train.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 07:34 AM_

Solved by PR #1412 (merged to dev). Closing manually — dev-targeted Closes does not auto-close.

