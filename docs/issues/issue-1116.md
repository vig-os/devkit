---
type: issue
state: closed
created: 2026-07-15T12:31:21Z
updated: 2026-07-15T14:10:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1116
comments: 1
labels: bug, priority:high, area:workspace, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:02.333Z
---

# [Issue 1116]: [.vig-os upgrade blanks DEVKIT_TAG_PREFIX / DEVKIT_FLOATING_TAGS (silent release-tag regression)](https://github.com/vig-os/devkit/issues/1116)

## Summary

An `install.sh --force` upgrade resets the `DEVKIT_TAG_PREFIX` and
`DEVKIT_FLOATING_TAGS` keys in a consumer's `.vig-os` back to their empty
defaults, silently discarding values the consumer deliberately set. `.vig-os`
is documented as a declarative manifest whose values are resolved and written
back on (re)scaffold (`flag/env > .vig-os > prompt/default`), so consumer-set
values should survive an upgrade — as `DEVKIT_MODE` and the identity keys do.

## Impact

Release-integrity critical, and silent. Action-publishing repos set
`DEVKIT_TAG_PREFIX=v` (and typically `DEVKIT_FLOATING_TAGS=major,minor`) per
#1044 / #1045. After an upgrade that blanks them, the next release cuts bare
`X.Y.Z` tags instead of `vX.Y.Z` and stops force-moving `v0` / `v0.X` — breaking
every consumer pinned `uses: owner/repo@v0`. Nothing warns (contrast #1093,
which added a warning for the related flake-pin ↔ `DEVKIT_VERSION` skew class).

## Reproduction

Consumer `vig-os/commit-action` (direnv mode), upgrading 1.2.0 → 1.2.1 with
`.vig-os` containing `DEVKIT_TAG_PREFIX=v` and `DEVKIT_FLOATING_TAGS=major,minor`:

```
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/1.2.1/install.sh \
  | bash -s -- --force --version 1.2.1 .
```

Resulting `.vig-os` diff:

```diff
-DEVKIT_TAG_PREFIX=v
+DEVKIT_TAG_PREFIX=
-DEVKIT_FLOATING_TAGS=major,minor
+DEVKIT_FLOATING_TAGS=
```

`DEVKIT_VERSION`, `DEVKIT_MODE`, `DEVKIT_PROJECT/ORG/REPO` were all preserved
correctly — only the tag-scheme keys were dropped.

## Expected

Consumer-set `DEVKIT_TAG_PREFIX` / `DEVKIT_FLOATING_TAGS` are preserved through
`--force` (resolve `flag/env > existing .vig-os > default`), the same as the
mode and identity keys.

## Context

Found while adopting 1.2.1 downstream to fix a release-workflow failure
(`vig-os/commit-action#79`, PR `vig-os/commit-action#80`); we restored the two
values by hand as part of that PR.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:10 PM_

Fixed by #1123 (merged into `dev`). `DEVKIT_TAG_PREFIX` / `DEVKIT_FLOATING_TAGS` are now read before the template overwrite and written back, mirroring the `DEVKIT_MODULES` preservation pattern; regression-tested in `tests/bats/init-workspace.bats`. Ships with the next patch release.

