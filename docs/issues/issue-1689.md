---
type: issue
state: closed
created: 2026-09-25T07:09:25Z
updated: 2026-09-25T12:32:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1689
comments: 2
labels: bug, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:46.771Z
---

# [Issue 1689]: [[BUG] prepare-changelog prepare silently deletes bullets not under a ### subsection while validate accepts them](https://github.com/vig-os/devkit/issues/1689)

## Description

`prepare-changelog validate` and `prepare-changelog prepare` disagree about what counts as content under `## Unreleased`, and the gap silently destroys entries.

- `validate` (`prepare_changelog.py:176-186`) reports "has content" when **any** line under `## Unreleased` starts with `-` (`re.search(r"^\s*-", ...)`).
- `prepare` (`prepare_changelog.py:18-40`, `_parse_subsections`) extracts bullets **only** from `### <Standard section>` subsections.

A bullet written directly under `## Unreleased` with no `###` header therefore passes `validate`, and `prepare` then drops it: the new `## [X.Y.Z] - TBD` section is written **empty**, `## Unreleased` is reset to the six empty headers, the bullet is gone from the file, and the command exits **0** with only a `⚠ Warning: No content found in Unreleased section` on stdout.

This became reachable in production with #1676 and #1682. `main` may now carry a non-empty `## Unreleased` (#1676), and `prepare-hotfix.yml`'s new `Classify main's Unreleased section` step (#1682, `.github/workflows/prepare-hotfix.yml:176-194`) chooses `MODE=prepare` **by calling `validate`** — so it selects the freeze path on exactly the input `prepare` cannot freeze. The classifier guards the bare-Unreleased duplication hazard the header comment describes, but not this one. The dry probe in the same step (`uv run prepare-changelog "$MODE" "$VERSION" CHANGELOG.md`) also passes, because the exit code is 0.

Devkit's own `main` cannot hit this today: `reset_unreleased` always leaves the six `###` headers, and the mirror hook preserves them. The exposed case is a hand-edited changelog (a release-neutral PR authored on `main`, or a consumer repo, since the same `prepare-hotfix.yml` step ships in the scaffold under `assets/workspace/`).

## Steps to Reproduce

```sh
mkdir repro && cd repro
printf '# Changelog\n\n## Unreleased\n\n- **Loose bullet without a subsection header** ([#1](x))\n\n## [1.0.0] - 2026-01-01\n\n### Fixed\n\n- old fix\n' > CHANGELOG.md
uv run --project packages/vig-utils prepare-changelog validate CHANGELOG.md; echo "validate rc=$?"
uv run --project packages/vig-utils prepare-changelog prepare 1.0.1 CHANGELOG.md; echo "prepare rc=$?"
cat CHANGELOG.md
```

## Expected Behavior

Either `validate` rejects loose bullets (so the classifier picks a path that refuses rather than one that loses data), or `prepare` refuses with a non-zero exit when `validate` says there is content but `_parse_subsections` finds none. In no case should `prepare` exit 0 having removed a bullet from the file.

## Actual Behavior

```
✓ CHANGELOG validation passed
✓ Unreleased section exists with content
validate rc=0
✓ Prepared CHANGELOG for version 1.0.1
⚠ Warning: No content found in Unreleased section
✓ Created fresh Unreleased section
prepare rc=0
```

Resulting file: `## Unreleased` with six empty headers, `## [1.0.1] - TBD` **empty**, the loose bullet gone. The loss is only caught later and indirectly, when `release.yml`'s `prepare-changelog validate --version` refuses the empty section, by which point the entry text exists nowhere in git except history.

## Environment

- **Ref**: `dev` @ `1c4cf837` (post-#1682 merge commit `0e8628ff`)
- **Tool**: `packages/vig-utils` `prepare-changelog`, run via `uv run`
- **Workflows affected**: `.github/workflows/prepare-hotfix.yml` and the scaffold copy `assets/workspace/.github/workflows/prepare-hotfix.yml`

## Additional Context

Related: #1676 (main may carry unshipped entries), #1679 / #1682 (classifier that selects `prepare`), #612 (the duplicate-bullet dedupe in `_merge_sections`). The sibling hazard, `prepare` duplicating the previous release's entries on a **bare** `## Unreleased` (no headers, no bullets), is still present in `prepare` but is masked by the classifier because `validate` returns 1 there; worth fixing in the same change so `prepare` is safe on every input shape rather than relying on the caller.

## Possible Solution

Make the two commands share one notion of content, and make `prepare` fail closed:

1. In `prepare`, compute `_parse_subsections` first; if `validate`'s bullet check is true but the parsed subsections are empty, exit non-zero with a message naming the loose lines, and do not rewrite the file.
2. Make `validate` reject bullets that are not under a recognised `### ` header, so the classifier never selects `prepare` for them.
3. Add tests for the three input shapes: bullets under `### Fixed` (freeze), loose bullets (refuse), bare section (seed / refuse-if-forced).

## Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 07:25 AM_

**Correction to the report above:** the bare-`## Unreleased` duplication hazard is **not** masked by the #1682 classifier. The old `validate` used the same unbounded body regex (`## Unreleased\s*\n(.*?)(?=\n## \[|\Z)`): on a bare section the heading's `\s*\n` consumes the blank-line separator, the `\n## \[` lookahead can never match, and the capture runs to end of file — so `validate` sees the *previous release's* bullets and exits **0**. The classifier would therefore have chosen `prepare`, which then copies the previous release's subsections into the new version section. Reproduced with the `dev` code:

```
$ printf '# Changelog\n\n## Unreleased\n\n## [1.0.0] - 2026-01-01\n\n### Fixed\n\n- old fix\n' > CHANGELOG.md
$ prepare-changelog validate CHANGELOG.md
✓ CHANGELOG validation passed
✓ Unreleased section exists with content
$ echo $?
0
```

Both hazards share one root cause (the unbounded capture plus two different notions of "content"), and the fix on `bugfix/1689-prepare-changelog-loose-bullets` bounds the body at the next `^## ` heading and makes `validate` and `prepare` agree.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 12:32 PM_

Fixed in #1691 (merged to `dev` 2026-09-25, 1d2e7106): `prepare-changelog` now fails closed on content it cannot freeze — loose bullets under `## Unreleased`, a bare Unreleased header, a `[X.Y.Z] - TBD` twin, duplicate `###` headings — and `validate --version` rejects the same shapes. Reaches `main` with the next train.

