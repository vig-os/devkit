---
type: issue
state: closed
created: 2026-07-14T11:21:18Z
updated: 2026-07-14T12:18:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1055
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:26.709Z
---

# [Issue 1055]: [[BUG] Node justfile.project seed ships without the preserved provenance banner](https://github.com/vig-os/devkit/issues/1055)

## Problem

Cross-PR gap flagged in PR #1043 and PR #1042: the node recipe seed `assets/justfile.d/node.justfile.project` (#1027) lives **outside** `assets/workspace/`, so the #1036 banner pass never touches it. A Node consumer's first-scaffold `justfile.project` (seeded from it, replacing the uv template) therefore lacks the **preserved** banner every other consumer-owned file now carries — and the uv template it replaces *does* carry one, so the two first-scaffold outcomes are inconsistent.

## Fix

Extend the banner application to the seed inputs (e.g. include `assets/justfile.d/` in the sync-manifest banner pass with an explicit preserved classification, or an equivalent single-source mechanism). Do NOT hand-type the banner into the seed — hand-written banners are exactly what #1036 eliminated (they rot; see justfile.devc).

## Acceptance criteria

- [ ] A first-scaffolded Node `justfile.project` carries the preserved banner (bats assertion alongside the #1027 seeding tests)
- [ ] The banner text derives from the same SSoT as all others; `sync-manifest` gates tampering
- [ ] The gitignore fragments in `assets/gitignore.d/` are considered for the same treatment (they append into a *managed* file — decide and document whether fragments need no banner because the assembled `.gitignore` already opens with one)

Refs: #1036, #1027
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:18 PM_

Fixed in #1064 (merged to dev): seed inputs outside assets/workspace get banners via _SEED_BANNERS + apply_seed_banners, variant derived from the PRESERVE_FILES target each seed feeds (SSoT, tamper-gated). gitignore fragments deliberately un-bannered (they append into an already-bannered managed file) — documented in code.

