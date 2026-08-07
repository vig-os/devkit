---
type: issue
state: closed
created: 2026-08-07T09:31:16Z
updated: 2026-08-07T12:11:28Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1355
comments: 1
labels: bug, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:03.981Z
---

# [Issue 1355]: [release-publish extracts notes with unprefixed heading grep but prepare-changelog --tag-prefix v writes ## [vX.Y.Z]](https://github.com/vig-os/devkit/issues/1355)

In a repo that sets a tag prefix, the release pipeline writes one changelog
heading format and reads back a different one, so the published GitHub Release
gets empty notes.

## The mismatch

`prepare-changelog finalize` is invoked with the resolved prefix
(`assets/workspace/.github/workflows/release-core.yml:446`):

```
prepare-changelog finalize "$VERSION" "$RELEASE_DATE" CHANGELOG.md --tag-prefix "$TAG_PREFIX"
```

`--tag-prefix` composes the prefix onto the displayed heading
(`packages/vig-utils/src/vig_utils/prepare_changelog.py`, `finalize` docstring:
"``v`` -> ``## [v0.3.0](…/tag/v0.3.0)``"), so with `TAG_PREFIX=v` the CHANGELOG
ends up with:

```
## [v1.0.0](https://github.com/<org>/<repo>/releases/tag/v1.0.0) - 2026-08-06
```

`release-publish.yml:216-228` then extracts the notes with the **unprefixed**
version:

```yaml
env:
  VERSION: ${{ inputs.version }}
run: |
  awk -v version="$VERSION" '
    index($0, "## [" version "]") == 1 {found=1; next}
    /^## \[/ && found {found=0}
    found
  ' CHANGELOG.md > /tmp/release-notes.md
```

`inputs.version` is the bare semver (`1.0.0`); the prefix travels separately as
`inputs.tag_prefix`, and `PUBLISH_TAG` is built as `${TAG_PREFIX}${VERSION}`. So
the matcher looks for `## [1.0.0]` against a heading that reads `## [v1.0.0](…`
and never matches.

Note the link form itself is fine — `index($0, "## [1.0.0]") == 1` does match
`## [1.0.0](url) - date`, because the searched string is a prefix of the line.
The prefix is the only thing that breaks it.

## Result

The `[ ! -s /tmp/release-notes.md ]` fallback fires and the release is published
with the literal body `No changelog notes found for 1.0.0`. It fails soft: the
release exists, the tag is right, only the notes are empty, so nothing goes red.

Repos with no tag prefix are unaffected, which is why this has not surfaced —
prefixed repos are the minority.

## Where it was observed

Releasing `vig-os/org-config` `v1.0.0`, which uses `v` as its tag prefix and
mirrors this pipeline's steps manually.

## Suggested fix

Match on the composed tag in the extraction step — pass `tag_prefix` into the
step and search for `## [${TAG_PREFIX}${VERSION}]` — or have `finalize` keep the
heading unprefixed. Either way the writer and the reader must agree, and a
regression test over a prefixed repo would pin it (`tests/test_release_tag_prefix.py`
is the natural home).
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 10:38 AM_

Fixed on dev by PR #1359: the release-publish note extraction now takes the threaded tag_prefix input and matches both the composed heading (## [vX.Y.Z], written by finalize --tag-prefix on final releases) and the bare form (## [X.Y.Z] - TBD, which candidates still carry since finalize is gated on release_kind == final). Prefix-only matching — the issue's literal suggestion — would have moved the empty-notes bug onto the candidate path, so the reader accepts both; with an empty prefix the match is byte-identical to today's. Ships with the next devkit release.

