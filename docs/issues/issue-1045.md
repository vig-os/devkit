---
type: issue
state: closed
created: 2026-07-14T08:59:42Z
updated: 2026-07-14T10:12:28Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1045
comments: 1
labels: feature, priority:medium, area:ci, area:workflow, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:29.127Z
---

# [Issue 1045]: [[FEATURE] Opt-in floating major/minor tags moved at promote (DEVKIT_FLOATING_TAGS)](https://github.com/vig-os/devkit/issues/1045)

## Description

Opt-in **floating major/minor tags** moved by the scaffolded `promote-release.yml`, declared in the `.vig-os` manifest:

```ini
# .vig-os
DEVKIT_FLOATING_TAGS=major,minor
```

Default empty ⇒ no floating tags (today's behavior). When set, promotion of a **final** release force-moves `<prefix>X` (major) and/or `<prefix>X.Y` (minor) to the promoted release commit — e.g. promoting `v0.3.0` moves `v0` and `v0.3`.

## Problem Statement

GitHub Action consumers pin floating refs: `uses: vig-os/commit-action@v0`. That resolution is pure git-tag lookup — the tag named `v0` must exist and must track the latest accepted release.

- The devkit image has an analog already: `promote-release.yml` moves the GHCR `:latest` tag at promote time. Action repos got the GHCR logic stripped (correctly), but received **no replacement** for their floating pointer.
- Today `vig-os/commit-action` moves `v0`/`v0.2` by hand after each release — unautomated, easy to forget, and unprotected by the release gates.

Promote is the only correct moment: it is the post-acceptance gate (Release published, PR merged to `main`), exactly like `:latest`. RC candidates must never move floating tags.

## Proposed Solution

- New `.vig-os` key `DEVKIT_FLOATING_TAGS` (comma-separated subset of `major,minor`; empty/absent ⇒ off). Read via `resolve-toolchain`, passed into `promote-release.yml`.
- New step in the promote job, after Release publication and PR merge succeed: derive `X` / `X.Y` from the promoted version, compose with `DEVKIT_TAG_PREFIX` (depends on #1044), and force-push the floating tags at the release tag's commit. Idempotent (skip when already pointing there); final releases only.
- Push with the RELEASE_APP token so a tag ruleset can deny tag update/delete to everyone else — floating-tag moves become an app-exclusive, audited operation.
- Document in `docs/DOWNSTREAM_RELEASE.md`: floating tags are mutable by design and therefore never get a GitHub Release object (immutable releases would lock them).

## Alternatives Considered

- **Local `promote-release.yml` patch per consumer**: works today but duplicates the logic across both Action repos and drifts on every scaffold upgrade.
- **GitHub Release "latest" alias only**: does not affect `uses:` ref resolution — consumers need the git tag.
- **Bare `X` floating tags** for non-prefixed repos: allowed for free by composing with the prefix, but no known consumer wants it; the feature simply stays generic.

## Additional Context

Companion to #1044 (floating tag names compose with the prefix). Found while auditing `vig-os/commit-action`'s devkit-1.1.0 release stack; its `v0`/`v0.2` are currently hand-moved.

## Impact

- Off by default — no change for devkit or existing consumers.
- Gives Action-publishing consumers the standard `@vN` pinning contract with promote-gated, app-only tag moves.
- SemVer: minor.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 10:12 AM_

Implemented in #1051 (merged to dev): DEVKIT_FLOATING_TAGS (major,minor) moves prefix-composed floating tags in a new promote job gated on Release publication + main-merge success; idempotent, final-only, RELEASE_APP-token pushes. Documented in docs/DOWNSTREAM_RELEASE.md.

