---
type: issue
state: closed
created: 2026-07-28T11:39:15Z
updated: 2026-07-28T13:42:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1279
comments: 2
labels: bug, priority:medium, area:workflow, effort:small, semver:patch, security
assignees: none
milestone: 1.4.3
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:56.605Z
---

# [Issue 1279]: [sync-issues template: mirror-bootstrap step interpolates target-branch input into run block (zizmor template-injection)](https://github.com/vig-os/devkit/issues/1279)

## Description

The `DEVKIT_SYNC_TARGET` mirror-bootstrap step in the sync-issues template (`assets/workspace/.github/workflows/sync-issues.yml`) interpolates the `target-branch` workflow_dispatch input directly into a `run:` block:

```yaml
run: |
  set -euo pipefail
  TARGET="${{ github.event.inputs.target-branch || 'sync/issue-mirror' }}"
```

zizmor flags this as **template-injection (High confidence)** and the consumer zizmor gate (#1182) fails the render. First hit in the wild: vig-os/org-config#80 (first consumer to set `DEVKIT_SYNC_TARGET`) — the step only renders when the knob is set, which is why the #1182 hardening sweep never saw it.

## Fix

Standard env indirection, as used elsewhere in the template (cf. the `TARGET_BRANCH:` env pattern in the commit step):

```yaml
env:
  TARGET_INPUT: ${{ github.event.inputs.target-branch }}
run: |
  set -euo pipefail
  TARGET="${TARGET_INPUT:-sync/issue-mirror}"
```

org-config carries this exact forward-port locally in PR vig-os/org-config#80 until the template fix ships — its next devkit upgrade will re-introduce the finding if this isn't fixed first.

Surfaced 2026-07-28 while pointing org-config's sync at a mirror branch (#1227 mechanism).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 28, 2026 at 11:50 AM_

**Docs rider for the fix PR** (from the "should mirror mode optionally open a PR to main?" exploration, 2026-07-28 — verdict: don't build it, document the manual pattern):

Add a paragraph to the `DEVKIT_SYNC_TARGET` documentation (the `.vig-os` comment block and/or the sync-issues docs):

> Want the snapshots visible on `main`? Open a checkpoint PR at your own cadence: `gh pr create --base main --head <mirror-branch>`. Merges are conflict-free by construction — only the sync job writes `docs/issues/` and `docs/pull-requests/` — and subsequent checkpoints show only the new sync commits. Note the PR path subjects the generated markdown to the repo's full lint gate, which the direct mirror push never exercises.

Rationale for not automating: the mirror serves git-archival (clone-portable record), live issues remain the browsing/search surface, exactly one consumer (org-config) runs mirror mode today, and an automated PR would add daily update noise plus recurring lint friction on generated content. If more trunk consumers with protected mains appear, revisit with an ephemeral squashed staging branch + one standing auto-refreshed PR rather than PR-ing the permanently-diverging mirror.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 28, 2026 at 01:42 PM_

Fixed by PR #1287 (merged to dev, milestone 1.4.3). The bootstrap-step heredoc now routes the target-branch dispatch input through env (TARGET_INPUT); org-config can drop the #80 forward-port on its next devkit upgrade.

