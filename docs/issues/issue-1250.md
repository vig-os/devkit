---
type: issue
state: closed
created: 2026-07-22T12:59:04Z
updated: 2026-07-23T15:59:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1250
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-24T05:27:30.964Z
---

# [Issue 1250]: [Release freeze commit paints a guaranteed-red nix-image run on dev](https://github.com/vig-os/devkit/issues/1250)

## Description

Since #1236 dropped the `nix-image.yml` `paths:` allowlist, every `dev` push rebuilds the discovery image — including the changelog-freeze commit of a release train, which updates `CHANGELOG.md` (and its baked copy) but not the workspace manifest checksums. Those sync one commit later (`chore: sync workspace manifest`), so the freeze commit's image build fails its manifest test:

```
FAILED tests/test_image.py::TestFileStructure::test_manifest_files
AssertionError: Manifest file checksum mismatch: /root/assets/workspace/.devcontainer/CHANGELOG.md
```

Observed on the 1.4.1 train (2026-07-21): run on `3155ee6f` (freeze) red on both arches, run on `8e9c4c5d` (manifest sync, one minute later) green. Before #1236 the freeze push simply didn't trigger, so the window was invisible.

## Expected Behavior

No structurally-guaranteed red run per release train. Options:

- push freeze + manifest-sync as one push (single trigger at the healed head), or
- a `concurrency` group on the `dev` push trigger with `cancel-in-progress: true`, so the freeze build is superseded by the sync build instead of completing red.

Cosmetic/noise only — no artifact is wrong — but a red run every train trains people to ignore red.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 03:59 PM_

Fixed by PR #1251 (cancel superseded nix-image builds per ref), merged into `release/1.4.1` and shipped in [1.4.1](https://github.com/vig-os/devkit/releases/tag/1.4.1). Closing.

