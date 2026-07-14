---
type: issue
state: closed
created: 2026-07-14T07:26:38Z
updated: 2026-07-14T08:27:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1029
comments: 1
labels: bug, priority:medium, area:ci, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:33.239Z
---

# [Issue 1029]: [[BUG] Release pipeline is python-shaped: no artifact/bundle step for node/TS consumers, stale 'Sync Python dependencies' labels](https://github.com/vig-os/devkit/issues/1029)

### Description

Surfaced by the commit-action pilot (vig-os/commit-action#32). The scaffolded
release pipeline is Python-shaped and does not support building a non-Python
release artifact.

1. **No artifact/bundle step.** `release-core.yml` runs `just sync` + `just test`
   (language-neutral), but there is **no step that builds and commits a language
   artifact**. A JS GitHub Action must rebuild and commit `dist/index.js` (the
   `@vercel/ncc` bundle, referenced by `action.yml` `runs.main`) as part of a
   release — the pipeline has no `just bundle`/commit-dist step, so a Node action
   released through it would ship a stale or missing bundle.
2. **Stale Python step labels.** The sync step is named **"Sync Python
   dependencies"** (`release-core.yml:592`) though it runs `just sync`
   (= `npm ci` on a Node repo); `ci.yml` similarly comments `test — Pytest`.
   Misleading for non-Python consumers.

### Impact

Not yet hit — `commit-action` has not adopted the devkit release flow (no `dev`
branch). But as-is, a Node/TS consumer cannot release through the devkit pipeline
without shipping a stale `dist/`.

### Suggested fix

- Neutral step labels (e.g. "Sync dependencies", "Run tests").
- A language-aware / opt-in **artifact build** step for repos that ship a built
  artifact (e.g. run `just bundle` and commit `dist/` on release), gated by
  language/`DEVKIT_MODULES` or a project flag.

### Related

Node module #1027; pilot #32.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:27 AM_

Fixed in #1033 (merged to dev): neutral step labels, plus an opt-in release bundle step — the finalize job detects a `bundle` just recipe and commits `dist/` in the finalization commit, so JS Actions tag a fresh bundle.

