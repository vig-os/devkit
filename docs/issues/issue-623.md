---
type: issue
state: open
created: 2026-06-23T05:39:25Z
updated: 2026-06-23T05:43:44Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/623
comments: 0
labels: bug, area:ci, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T06:15:16.658Z
---

# [Issue 623]: [promote-release cleanup deletes RC tag but fails to delete the RC draft pre-release (orphans it permanently)](https://github.com/vig-os/devcontainer/issues/623)

## Description

RC **draft pre-releases** are still surviving in the `vig-os/devcontainer-smoke-test` repo after each release cycle, despite the cleanup added in #601 (fix for #600).

Current stranded state in the smoke-test repo:

| Release | draft | prerelease | git RC tag present? |
|---------|-------|------------|---------------------|
| `0.3.7-rc1` | ✅ true | ✅ true | ❌ deleted |
| `0.3.8-rc1` | ✅ true | ✅ true | ❌ deleted |

The #601 cleanup logic is reached and *attempts* the deletion, but the `gh release delete "$tag" --yes` call **fails for draft pre-releases**, while the code still falls through and deletes the git RC tag. Because the cleanup loop is seeded from `git ls-remote --tags ${VERSION}-rc*`, once the tag is gone the orphaned draft can never be re-discovered — it is stranded permanently.

## Root cause

Evidence from the `0.3.8` final promote-release run in the smoke-test repo (run `27982523396`, cleanup step `Delete RC draft pre-releases and git RC tags`):

```
Deleting RC draft pre-release 0.3.8-rc1 (draft pre-release)
WARN: failed to delete RC draft pre-release 0.3.8-rc1     <-- release delete FAILS (after 3 retries)
Deleting remote tag 0.3.8-rc1 (no GitHub Release)         <-- git tag deleted anyway
```

Two compounding bugs in the cleanup step (`assets/workspace/.github/workflows/promote-release.yml`, lines ~399-443; mirrored in the upstream `.github/workflows/promote-release.yml`, lines 602-647):

1. **`gh release delete <tag>` cannot resolve a draft release.** `gh release delete "$tag"` resolves the release via the *"Get a release by tag name"* API (`GET /repos/{o}/{r}/releases/tags/{tag}`), which **does not return draft releases**. So the delete fails with "release not found" even though the draft exists and was correctly identified from the *list-releases* response. The cleanup already fetched the matching release object (it reads `.draft`/`.prerelease` from it) — it should delete by **release id** via `gh api -X DELETE repos/${GITHUB_REPOSITORY}/releases/<id>` instead of `gh release delete <tag>`.

2. **The git RC tag is deleted unconditionally on fall-through, even when the release delete failed.** `gh release delete ... || echo "WARN: failed..."` swallows the failure, then control falls through to the tag deletion. This orphans the draft permanently, because:

3. **The loop is seeded from git tags, not from the releases list.** Candidate seed is `git ls-remote --tags --refs ... "${VERSION}-rc*"`. A draft whose tag has already been removed is invisible to this loop forever. Seeding from the *list-releases* endpoint (filtered to `draft && prerelease && tag ~ ^${VERSION}-rc[0-9]+$`) would make cleanup idempotent and self-healing for already-orphaned drafts.

## Steps to Reproduce

1. Run a downstream candidate cycle in `devcontainer-smoke-test` with `create-release=true` (the standard smoke-test dispatch) → a `X.Y.Z-rcN` git tag **and** a draft pre-release are created.
2. Run the final `X.Y.Z` cycle → `promote-release.yml` cleanup runs.
3. Observe the cleanup step log: `WARN: failed to delete RC draft pre-release X.Y.Z-rcN`, followed by `Deleting remote tag X.Y.Z-rcN`.
4. Check `gh release list --repo vig-os/devcontainer-smoke-test`: the `X.Y.Z-rcN` draft pre-release remains; its git tag is gone.

## Expected Behavior

After a final promote-release, no `X.Y.Z-rc*` draft pre-releases (nor their git tags) remain for the promoted base version. Cleanup should also reclaim already-orphaned drafts from prior cycles.

## Actual Behavior

The git RC tag is deleted but the RC draft pre-release survives and accumulates every release cycle. Drafts orphaned before their tag was removed can never be cleaned up by subsequent runs.

## Environment

- Repos: `vig-os/devcontainer` (SSoT) and deployed templates in `vig-os/devcontainer-smoke-test`
- Workflows: `assets/workspace/.github/workflows/promote-release.yml` (deployed, the one that runs in smoke-test) and `.github/workflows/promote-release.yml` (upstream, same latent bug)
- Observed on cleanup runs for finals `0.3.7` and `0.3.8` (2026-06-22)
- Prior work: #600 (original report), #601 / commit `09e780d` (incomplete fix)

## Possible Solution

In the cleanup step of **both** promote-release workflows:

1. Seed the loop (or a second pass) from the **list-releases** endpoint, selecting `draft == true && prerelease == true && tag_name ~ ^${VERSION}-rc[0-9]+$`, so orphaned drafts (no git tag) are also reclaimed and the step is idempotent.
2. Delete the draft by **release id**: `gh api -X DELETE "repos/${GITHUB_REPOSITORY}/releases/<id>"` (or `gh release delete <tag> --cleanup-tag` only if/when gh can resolve drafts), instead of `gh release delete <tag>` which can't resolve drafts.
3. **Gate the git-tag deletion on the release deletion succeeding** — do not fall through and delete the tag when the draft delete returned non-zero, to avoid permanently orphaning the draft.
4. Add a final verification pass that fails (loudly) if any `X.Y.Z-rc*` draft pre-release still exists for the promoted base version, mirroring the existing GHCR RC prune verification.

Clean up the two already-stranded drafts (`0.3.7-rc1`, `0.3.8-rc1`) in the smoke-test repo as part of the fix.

## Changelog Category

Fixed

