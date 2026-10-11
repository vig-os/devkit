---
type: issue
state: open
created: 2026-10-10T22:21:58Z
updated: 2026-10-10T22:21:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1858
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-11T08:37:36.288Z
---

# [Issue 1858]: [feat(changelog): support per-change fragments in consumer release preparation](https://github.com/vig-os/devkit/issues/1858)

## Problem
Parallel PRs edit the same Unreleased section of CHANGELOG.md and repeatedly conflict. vig-os/vigil#40 uses Git's union driver as an interim measure, but GitHub server-side merges do not provide a dependable equivalent and union merging still needs editorial review.

## Requested feature
Support consumer-owned changelog fragments, one file per change/issue, with Added/Changed/Fixed categories. Have release preparation deterministically assemble fragments into a single Unreleased/release section compatible with prepare_changelog.py, validate malformed/duplicate fragments in CI, preserve released history, and consume fragments only as part of release preparation. Document migration and the consumer-owned scaffold seam.

## Acceptance
Two parallel PRs adding distinct fragment files merge cleanly; release preparation includes both exactly once; validation catches invalid fragments; existing single-file consumers remain supported.

Refs: vig-os/vigil#40

