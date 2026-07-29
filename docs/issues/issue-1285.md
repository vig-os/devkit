---
type: issue
state: open
created: 2026-07-28T13:27:57Z
updated: 2026-07-28T13:27:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1285
comments: 0
labels: docs, priority:low, effort:small, area:docs
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:55.000Z
---

# [Issue 1285]: [docs(workspace): solo/private-repo adoption profile](https://github.com/vig-os/devkit/issues/1285)

### Description

A documented **solo/private-repo adoption profile**: the recipe a single-user consumer follows to adopt devkit without the team/traceability layer, expressed as a combination of existing knobs — and optionally, later, an installer `--profile solo` flag that writes the same manifest keys.

The profile (once the dependencies land):

```
--mode devcontainer --workflow trunk
DEVKIT_FEATURES_DISABLED="release sync-issues scanning skills worktree"   # 1284
DEVKIT_REFS_POLICY=optional                                               # 1282
```

plus the adoption notes that keep tripping solo adopters: default branch must be `main` (#1283), undotted `typos.toml` handling (#1280), zero-test Python repos (#1281).

### Documentation Type

Guide / how-to (new section in `docs/MIGRATION.md`, or a dedicated `docs/SOLO_ADOPTION.md` linked from README's install section).

### Target Files

- `docs/MIGRATION.md` (or new `docs/SOLO_ADOPTION.md`)
- `README.md` (one pointer line in the install/quick-start section)

### Related Code Changes

Depends on #1284 (feature opt-outs) and #1282 (Refs policy knob) — the guide documents those keys; without them it can only describe the delete-and-reprune workaround. The optional `--profile solo` installer flag is a small follow-up once both exist and should reference this issue.

### Acceptance Criteria

- [ ] A solo adopter can go from zero to a working scaffold (hooks + justfiles + devcontainer, no team layer) following one document, without discovering knobs by reading `init-workspace.sh`
- [ ] The guide states what is *kept* (hook stack, commit-msg validation, agent-identity enforcement, upgrade path) as clearly as what is dropped
- [ ] Cross-links: #1280, #1281, #1282, #1283, #1284

### Changelog Category

Added

### Additional Context

Distilled from a full adoption evaluation of devkit for a private single-user data repo (beancount ledger): the solo-valuable core is the hook stack, commit hygiene, and the managed upgrade path; the friction is entirely in the issue/PR/release/scanning layer. That evaluation produced the five issues referenced above; this guide is the piece that turns them into a repeatable adoption story.

