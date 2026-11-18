---
type: issue
state: open
created: 2026-11-11T04:13:22Z
updated: 2026-11-11T04:13:22Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2070
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-11T09:09:55.425Z
---

# [Issue 2070]: [Allow candidate releases to stamp X.Y.Z-rcN into a commit before tagging](https://github.com/vig-os/devkit/issues/2070)

## Problem

A downstream project whose binary reports its own version (e.g. `tool --version`, a package `version` attribute) wants a release candidate `X.Y.Z-rcN` to report exactly `X.Y.Z-rcN`.

Today that is impossible without editing managed workflows:

- `prepare-release.yml` calls the prepare-release extension once, with `version = X.Y.Z`, before any candidate exists, so it can only stamp the base `X.Y.Z`.
- `release-core.yml` computes `-rcN` at publish time and `release-publish.yml` tags the unchanged release-branch tip (`finalize_sha`) with a lightweight tag. Candidate mode keeps branch content unchanged.
- The `release-extension.yml` seam runs between those two steps but is capped at `contents: read`, so it cannot push a commit carrying `-rcN`.
- A second candidate cut from the same commit cannot differ in content either.

So a candidate can only report the base version (we additionally embed the source revision to make candidates identifiable).

## Request

Let candidate mode stamp `X.Y.Z-rcN` into a commit before tagging, for example one of:

1. a pre-tag, write-capable consumer seam (receives `publish_version`, may add a commit on the release branch that the tag then points at), or
2. a built-in, opt-in `DEVKIT_VERSION_FILES`-style manifest key listing files whose version field is rewritten to `publish_version` in a candidate commit, with finalize restoring/stamping `X.Y.Z`.

Either must keep the existing guarantees (rollback on failure, tag created only after the stamped commit exists, final tag on a commit carrying exactly `X.Y.Z`).

