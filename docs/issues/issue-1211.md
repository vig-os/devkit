---
type: issue
state: open
created: 2026-07-17T20:27:21Z
updated: 2026-07-17T20:27:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1211
comments: 0
labels: docs, priority:low, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:20.303Z
---

# [Issue 1211]: [workflow-model: docs + ADR + plan doc](https://github.com/vig-os/devkit/issues/1211)

Part of #1205.

- `docs/RELEASE_CYCLE.md`: "Workflow models" section (gitflow default vs trunk).
- `docs/DOWNSTREAM_RELEASE.md`: note `sync-main-to-dev` is gitflow-only.
- `docs/MIGRATION.md`: "workflow models" section (mirror the delivery-modes framing + destructive-switch preflight + orphan-`dev`-branch cleanup caveat).
- README / CLAUDE: one-line knob mention.
- New ADR in `docs/rfcs/` (structural-vs-runtime + compose-not-combine) + `docs/plans/` plan doc.
- `docs/generate.py` unchanged (branch prose is hand-maintained).

Refs: #1205
