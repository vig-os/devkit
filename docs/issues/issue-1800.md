---
type: issue
state: closed
created: 2026-10-01T14:09:11Z
updated: 2026-10-01T17:46:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1800
comments: 1
labels: bug, priority:high
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:22.526Z
---

# [Issue 1800]: [fix: actionlint opt-out leaves two blank lines that fail the consumer's yamllint](https://github.com/vig-os/devkit/issues/1800)

### Description

With `actionlint` in `DEVKIT_FEATURES_DISABLED`, the scaffold renders a `.pre-commit-config.yaml` that fails the consumer's own `yamllint` hook. Found by the #1762 consumer matrix (`features-disabled` cell).

### Steps to Reproduce

1. Seed an empty dir with a `.vig-os` containing `DEVKIT_FEATURES_DISABLED=actionlint`.
2. Render: `init-workspace.sh --no-prompts --mode both`.
3. `git init && git add -A && git commit`, then `prek run yamllint --all-files`.

### Expected Behavior

The rendered config passes every hook it ships.

### Actual Behavior

`.pre-commit-config.yaml:90:1: [error] too many blank lines (2 > 1)`

### Environment

devkit 1.16.0 and 1.17.0 (template shape since #1660).

### Additional Context

`render_actionlint_optout` (`assets/init-workspace.sh`, ~2517) deletes the lines from `# >>> devkit:actionlint` to `# <<< devkit:actionlint`, but leaves the blank lines on both sides, so two blank lines end up adjacent.

### Possible Solution

Have the excision also drop one adjacent blank line (or restructure the sentinels so the block owns its separating blank line). Pin with a bats render that runs yamllint over the result.

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 05:46 PM_

Fixed by #1804 (merged to `dev`, ships with the next release). Consumers already affected are not auto-repaired on upgrade; delete the one extra blank line by hand.

