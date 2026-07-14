---
type: issue
state: closed
created: 2026-07-14T08:59:31Z
updated: 2026-07-14T10:12:26Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1044
comments: 1
labels: feature, priority:high, area:ci, area:workflow, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:29.537Z
---

# [Issue 1044]: [[FEATURE] Per-repo release tag prefix (DEVKIT_TAG_PREFIX) for Action-publishing consumers](https://github.com/vig-os/devkit/issues/1044)

## Description

Add a per-repo release **tag prefix** to the scaffolded release pipeline, declared in the `.vig-os` manifest:

```ini
# .vig-os
DEVKIT_TAG_PREFIX=v
```

Absent/empty ⇒ today's bare `X.Y.Z` tags (no behavior change for devkit or any current consumer). When set, the prefix is applied **only at the publishing edge** — the pushed tag name and the changelog release link — while everything internal stays bare.

## Problem Statement

GitHub Action repos (`vig-os/commit-action`, `vig-os/sync-issues-action`) publish `v`-prefixed tags, per the ecosystem convention (`actions/checkout@v5`). `commit-action`'s entire history is `v`-prefixed (`v0.1.0` … `v0.2.0`, plus floating `v0`/`v0.2`), its README pins `@v0.1.5`, and its changelog headings are `## [v0.2.0](…/releases/tag/v0.2.0)`.

The devkit release pipeline hardcodes bare tags end to end:

- `release-core.yml` computes `PUBLISH_VERSION="$VERSION"` / `"${VERSION}-rc${NEXT_RC}"` (`assets/workspace/.github/workflows/release-core.yml:232,260,263`) and discovers existing RC numbers with a bare-tag pattern.
- `release-publish.yml` pushes `git tag -a "$PUBLISH_VERSION"` (`assets/workspace/.github/workflows/release-publish.yml:169`) and creates the GitHub Release under the same name.
- `prepare-changelog finalize` generates the release link as `releases/tag/{version}` (`packages/vig-utils/src/vig_utils/prepare_changelog.py:463`) — with a `v`-prefixed tag the link 404s.

So an Action repo running the scaffold as-is gets a tag scheme that breaks continuity with its published history and its consumers' pins. Tag schemes are inherently per-repo; the pipeline just doesn't expose the knob.

## Proposed Solution

Thread one optional value through the existing plumbing:

1. **`.vig-os`**: new key `DEVKIT_TAG_PREFIX` (default empty). The manifest header already designates it as the home for per-project devkit flags; consumers parse line-based and ignore unknown keys, so this is forward/backward compatible.
2. **`resolve-toolchain`**: read the key, emit a `tag-prefix` output.
3. **`release.yml`**: pass it as an input to the `workflow_call` children.
4. **Prefix-aware call sites** (mechanical `PUBLISH_TAG="${TAG_PREFIX}${PUBLISH_VERSION}"`):
   - `release-core.yml` — `publish_meta` (RC discovery pattern + publish tag), `tag_state` check against the finalize SHA.
   - `release-publish.yml` — tag create/push, `gh release create` tag + title.
   - `prepare-release.yml` — the "tag must not exist" validation.
   - `promote-release.yml` — release/tag validation and RC tag cleanup.
5. **`prepare-changelog finalize`**: new `--tag-prefix` option; applies to the link URL **and** the displayed heading (`## [v0.3.0](…/tag/v0.3.0) - DATE`), so prefixed repos keep heading continuity. Empty prefix reproduces today's output byte-for-byte. `validate`/`prepare`/`reset` are unaffected (they only touch `## Unreleased` / `- TBD` headings, which stay bare).

**Invariant that keeps the diff small**: the `version` workflow input, the `release/X.Y.Z` branch name, and the freeze heading `## [X.Y.Z] - TBD` all stay bare everywhere. The prefix is composed at the last moment, only where a tag name or tag URL is emitted.

## Alternatives Considered

- **Repo variable** (`vars.RELEASE_TAG_PREFIX`): works, but lives outside the repo (not versioned, invisible to scaffold tooling) and breaks the "`.vig-os` is the single per-project manifest" pattern.
- **Consumer-local edits** of the scaffolded release workflows: permanent drift in every Action repo, re-patched on every devkit upgrade — exactly what the scaffold model is meant to avoid.
- **Switching Action repos to bare tags**: breaks the GitHub Actions ecosystem convention, existing consumer pins (`@v0.1.5`), and leaves mixed tag/changelog history.

## Additional Context

Found while auditing `vig-os/commit-action`'s devkit-1.1.0 release stack before its first release through the pipeline. Related: floating major/minor tags (`v0`, `v0.2`) are a separate opt-in promote-time concern — filed separately; it composes with this prefix.

## Impact

- Fully backward compatible: absent/empty key ⇒ current behavior for devkit and all existing consumers.
- Unblocks `vig-os/commit-action` and `vig-os/sync-issues-action` releasing through the scaffold without local drift.
- SemVer: minor (new opt-in capability in scaffold + `vig-utils`).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 10:12 AM_

Implemented in #1051 (merged to dev): DEVKIT_TAG_PREFIX in .vig-os, threaded resolve-toolchain → release.yml → all tag-emitting call sites; prepare-changelog gained --tag-prefix (empty prefix byte-identical). Internal version/branch/heading names stay bare per the issue's invariant.

