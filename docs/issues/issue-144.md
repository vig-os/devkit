---
type: issue
state: open
created: 2026-02-21T21:45:19Z
updated: 2026-06-23T06:56:37Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/144
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:57.882Z
---

# [Issue 144]: [[BUG] generate-docs pre-commit hook misses new skill directories](https://github.com/vig-os/devcontainer/issues/144)

### Description

The `generate-docs` pre-commit hook does not trigger when skill directories are added or modified under `.cursor/skills/`. This means `docs/SKILL_PIPELINE.md` can become stale without the developer noticing during local commits.

### Problem Statement

The hook's `files` filter only matches:

```
^(docs/templates/.*\.j2|docs/narrative/.*\.md|scripts/requirements\.yaml|justfile)$
```

`docs/generate.py` scans `.cursor/skills/*/SKILL.md` to build the skills table in `SKILL_PIPELINE.md`. When a new skill directory is added (e.g. `pr_solve`), the hook does not fire during local commits because the changed files don't match the filter. CI catches it with `--all-files`, but the developer only finds out after pushing.

This caused the CI failure on PR #142.

### Proposed Solution

Add `.cursor/skills/` to the hook's `files` pattern:

```yaml
files: ^(docs/templates/.*\.j2|docs/narrative/.*\.md|scripts/requirements\.yaml|justfile|\.cursor/skills/.*)$
```

This ensures the hook fires whenever skills are added, removed, or modified.

### Alternatives Considered

- **Do nothing** — CI catches it with `--all-files`, but the feedback loop is slow and creates noise.
- **Add `git add docs/SKILL_PIPELINE.md` to the hook entry** — The hook already auto-stages `README.md`, `CONTRIBUTE.md`, and `TESTING.md`, but `SKILL_PIPELINE.md` is missing from the `git add` list. Both the trigger pattern and the staging list should be updated together.

### Impact

Prevents a class of CI failures where generated docs are stale after adding or modifying skills.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

#626 (part of #625) moves skills from `.cursor/skills/` to `.claude/skills/`, changing **both** `docs/generate.py`'s scan path and the pre-commit hook's `files` filter — which absorbs this fix. Will close/redirect when #626 lands.

