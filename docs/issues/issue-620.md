---
type: issue
state: closed
created: 2026-06-22T12:47:49Z
updated: 2026-06-22T21:04:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/620
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T06:15:17.031Z
---

# [Issue 620]: [[BUG] prepare-release PR-body extraction truncates at inline '## [' in changelog bullets](https://github.com/vig-os/devcontainer/issues/620)

## Description

The "Extract CHANGELOG content for PR body" step in `prepare-release` truncates
the release PR body when a `## [X.Y.Z]` version entry contains the literal text
`## [` anywhere in its bullets (e.g. a changelog entry that quotes a heading like
`` `## [X.Y.Z] - TBD` ``). Everything after that inline match is dropped from the
PR body.

## Observed (0.3.8)

The release PR (#619) body rendered only the first changelog bullet:

```
## [0.3.8] - TBD

### Fixed

- **Prevent prepare-release from branching ... (#617)**
```

— omitting the rest of #617 and the entire #612 entry. The CHANGELOG on
`release/0.3.8` is correct; only the extracted PR body is truncated.

## Root cause

```bash
CHANGELOG_CONTENT=$(sed -n "/## \[$VERSION\]/,/## \[/p" CHANGELOG.md | sed '$d')
```

The range-end pattern `/## \[/` is **unanchored**, so it matches the first line
containing `## [` *anywhere*, including inline backtick-quoted text inside a
bullet. The range therefore closes early and the tail of the section is lost.

## Proposed fix

Anchor both range patterns to the start of line so only real column-0 version
headings delimit the section:

```bash
sed -n "/^## \[$VERSION\]/,/^## \[/p" CHANGELOG.md | sed '$d'
```

Apply to both copies (identical step):
- `.github/workflows/prepare-release.yml`
- `assets/workspace/.github/workflows/prepare-release.yml`

## Refs

Surfaced on the 0.3.8 release PR (#619). Latent bug, exposed by changelog entries
for #617/#612 that quote `## [X.Y.Z]` headings.

---

# [Comment #1]() by [c-vigo]()

_Posted on June 22, 2026 at 09:04 PM_

Fixed via #621 and shipped in [0.3.8](https://github.com/vig-os/devcontainer/releases/tag/0.3.8). The PR-body changelog extraction now anchors its sed range to start-of-line headings, so inline backtick-quoted `## [X.Y.Z]` text no longer truncates the body. Confirmed on PR #619's refreshed body.

