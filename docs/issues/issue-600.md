---
type: issue
state: open
created: 2026-06-19T06:36:40Z
updated: 2026-06-19T06:36:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/600
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-19T07:20:03.253Z
---

# [Issue 600]: [promote-release cleanup never prunes RC draft pre-releases (and their tags)](https://github.com/vig-os/devcontainer/issues/600)

## Description

The `promote-release.yml` cleanup job prunes RC GHCR images/signatures and deletes RC git tags, but it **never removes RC draft pre-releases** — and because of that, it also leaves their git tags behind.

The "Delete git RC tags without GitHub Release" step skips any tag that has *any* GitHub Release attached:

```bash
if ... tag_name == $tag ...; then
  echo "Skipping tag $tag (GitHub Release exists)"
  continue
fi
```

For adopters that publish RC **draft pre-releases** during candidate dispatch (e.g. the smoke-test repo, which passes `create-release=true`), every release cycle therefore leaves a `X.Y.Z-rcN` draft pre-release **and** its tag behind. They accumulate indefinitely.

## Evidence

In `vig-os/devcontainer-smoke-test`, before manual cleanup, every past release had left a stranded RC draft pre-release + tag:

```
0.3.6-rc2  draft=true prerelease=true
0.3.5-rc1  draft=true prerelease=true
0.3.4-rc1  draft=true prerelease=true
0.3.3-rc1  draft=true prerelease=true
```

The upstream `devcontainer` repo is unaffected because it does not publish RC draft pre-releases — but the gap lives in the shared workspace template that adopters consume.

## Expected Behavior

After a successful promote, the cleanup should remove RC artifacts for the base version **including draft pre-releases**: delete the RC draft pre-release, then delete its git tag.

## Actual Behavior

RC draft pre-releases and their tags are skipped and persist forever.

## Proposed Fix

In the cleanup job of `promote-release.yml`, before/within the RC-tag step, delete RC **draft pre-releases** for `${VERSION}` first, then delete the tag. Guard strictly to avoid ever touching a published release:

- Only delete releases where `draft == true && prerelease == true` and `tag_name` matches `^${VERSION}-rc[0-9]+$`.
- After deleting the draft, the existing "no GitHub Release" tag-deletion will remove the tag (or delete the tag in the same step).

Apply to `assets/workspace/.github/workflows/promote-release.yml` (the adopter-facing SSoT). Mirror the change in the root `.github/workflows/promote-release.yml` for parity even though upstream does not currently create RC drafts.

## Notes

The current `0.3.6` RC artifacts (rc1/rc2 GHCR images, signatures, git tags) were pruned correctly by the existing logic; only the smoke-test's RC **draft pre-releases** were stranded, and have now been manually cleaned. This issue tracks the automated fix so they do not recur.

## Changelog Category

Fixed

