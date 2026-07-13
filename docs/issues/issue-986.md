---
type: issue
state: closed
created: 2026-07-13T05:45:00Z
updated: 2026-07-13T10:58:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/986
comments: 1
labels: bug, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:56.157Z
---

# [Issue 986]: [[BUG] Renovate cannot resolve digest for sigstore/cosign-installer (comment names nonexistent v4 tag)](https://github.com/vig-os/devkit/issues/986)

## Description

The dependency dashboard reports:

> Renovate failed to look up the following dependencies: Could not determine new digest for update (github-tags package `sigstore/cosign-installer`).
> Files affected: `.github/workflows/promote-release.yml`, `.github/workflows/release.yml`

Both workflows pin the action as:

```yaml
uses: sigstore/cosign-installer@cad07c2e89fa2edd6e2d7bab4c1aa38e53f76003  # v4
```

For digest-pinned actions, Renovate reads the trailing comment as the current version and resolves that tag back to a commit via the `github-tags` datasource. `sigstore/cosign-installer` publishes no floating `v4` tag (only exact tags `v4.0.0`–`v4.1.2`, plus a legacy floating `v3`), so the lookup of `refs/tags/v4` 404s and Renovate cannot compute a digest.

The pinned SHA `cad07c2e` actually corresponds to tag `v4.1.1`.

## Steps to Reproduce

1. Open the Renovate dependency dashboard issue
2. See the digest-lookup warning for `sigstore/cosign-installer`

## Expected Behavior

Renovate resolves the version comment to a real tag and keeps the digest pin updated automatically.

## Fix

Bump the pin in both workflows to the latest release, with a comment naming a real tag:

```yaml
uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6  # v4.1.2
```

All other digest-pinned actions in the repo use comments that resolve to real tags (verified against upstream), so this is the only affected dependency.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 10:58 AM_

Resolved by #987 (merged to `dev`). Closing.

