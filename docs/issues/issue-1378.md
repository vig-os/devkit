---
type: issue
state: closed
created: 2026-08-07T15:20:51Z
updated: 2026-08-07T16:35:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1378
comments: 1
labels: bug, priority:medium, area:ci, area:workspace, effort:medium, semver:minor, security
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:58.092Z
---

# [Issue 1378]: [[BUG] Consumer scaffold still publishes unsigned annotated release tags (downstream #1370)](https://github.com/vig-os/devkit/issues/1378)

## Summary

[#1370](https://github.com/vig-os/devkit/issues/1370) fixed devkit's **own**
release chain: the version tag is now a lightweight `refs/tags/<version>` ref
instead of an annotated tag object with an unsignable bot tagger (PR
[#1374](https://github.com/vig-os/devkit/pull/1374), merged to `dev`).

The **consumer scaffold** still has the defect. Every repo devkit scaffolds
publishes its release tags through
`assets/workspace/.github/workflows/release-publish.yml`, which does:

```yaml
      - name: Configure git
        env:
          GIT_USER_NAME: ${{ inputs.git_user_name }}
          GIT_USER_EMAIL: ${{ inputs.git_user_email }}
        run: |
          git config user.name "$GIT_USER_NAME"
          git config user.email "$GIT_USER_EMAIL"

      - name: Create and push tag
        ...
          git tag -a "$PUBLISH_TAG" -m "Release $PUBLISH_TAG"
          ... git push origin "$PUBLISH_TAG" ...
```

So every consumer's `X.Y.Z` tag is an annotated tag object whose tagger is a
GitHub App identity. The reasoning from #1370 transfers unchanged: an App has no
registrable GPG/SSH key, and `POST /git/tags` is not signed server-side either,
so the object reports `verification.reason: "unsigned"` permanently. There is no
"sign it" variant — the only fix is to not create a tag object.

## Why this is worth its own issue

The scaffold is already **internally inconsistent about this**. The same
scaffold's `promote-release.yml` creates the *floating* tags as lightweight refs
via `POST /git/refs` (`move_tag`, #1045/#1157). So on a consumer today:

- `vX` and `vX.Y` — lightweight refs, nothing unsigned;
- `vX.Y.Z` — annotated tag object, permanently `unsigned`.

The version tag is the one users pin and audit.

## Scope

**Change**

- `assets/workspace/.github/workflows/release-publish.yml`
  - replace "Configure git" + "Create and push tag" with a single ref-creating
    step mirroring `release.yml`'s **Create release tag** step from
    [PR #1374](https://github.com/vig-os/devkit/pull/1374):
    `gh api -X POST repos/{owner}/{repo}/git/refs -f ref=refs/tags/<tag> -f sha=<release commit>`,
    keeping the `tag_already_exists` skip and the create-race verification
    (accept only when the existing ref already resolves to the release commit).
  - the `git_user_name` / `git_user_email` **`workflow_call` inputs** of
    `release-publish.yml` (and the two pass-throughs in the scaffold
    `release.yml`) become dead and should go with it.

**Do NOT remove** the `git-user-name` / `git-user-email` `workflow_dispatch`
inputs of the scaffold `release.yml` itself — its rollback job still checks out
the release branch and writes a commit with that identity. Only the
`release-publish` leg is dead. (This is the one asymmetry with #1374, where the
publish job was the sole consumer and the inputs could go entirely.)

**Two behaviours that must be carried over, not dropped**

1. **GH013 tombstone detection** (#1319, pinned by
   `tests/test_release_tombstone_detection.py`). The current code greps `git
   push` stderr for `GH013|creations restricted` to diagnose "this version name
   is burned by release immutability — re-cut as the next patch". `POST
   /git/refs` fails with a different shape (HTTP 422 + JSON body), so the
   signature match has to be re-derived against the API error and the shape test
   updated. Losing this silently regresses a tombstoned release to an opaque
   error — exactly the regression #1319 was filed to prevent.
2. **`TAG_PREFIX` composition** (#1044): the tag name is
   `"${TAG_PREFIX}${PUBLISH_VERSION}"`, not the bare version.

**Docs whose wording goes stale (the peel logic itself should stay)**

- `assets/workspace/.github/workflows/promote-release.yml` — the comment
  "release-publish.yml creates an ANNOTATED tag, so peel it (object.type ==
  "tag")". Keep the peel: consumers that released *before* this change still
  have annotated tags and must keep resolving. Fix the comment.
- `docs/MIGRATION.md` (~L1028) — the first-release floating-tags runbook says
  "`release-publish.yml` creates an **annotated** tag, so peel it to the
  underlying commit first". Same treatment: keep the `object.type = tag`
  fallback, correct the claim.

## Blast radius — why this rides a release, not a hotfix

`release-publish.yml` is a **devkit-managed scaffold file**. Changing it changes
every consumer's stamped workflow: it lands only when a consumer re-scaffolds
(`install.sh --force` / `devkit-upgrade.yml`), and until then the
`scaffold-drift` CI gate flags them. That is precisely why it was kept out of
PR #1374 — that PR was a devkit-internal fix with no consumer surface, and
bundling this would have drifted every consumer for it.

Sequence it as: land on `dev` -> devkit release -> consumers pick it up on their
next `devkit-upgrade`. No consumer action is required beyond the normal upgrade;
existing annotated tags are left as they are (rewriting published tags is
forbidden by the forward-fix policy, and immutable releases lock them anyway).

## Optional to bundle

`assets/workspace/.github/workflows/release-publish.yml`'s checkout keeps
`persist-credentials: true` so `git push` can authenticate. Once the tag is
created through the API, the only remaining git-remote use is `git ls-remote
origin`, so the persisted credential is near-dead and could be dropped in the
same pass. The identical loose end exists in devkit's own `release.yml` publish
job after PR #1374 — left there deliberately to keep that diff minimal, and
worth closing in both places at once. Zizmor flags persisted credentials
(`artipacked`), so this also removes a standing finding.

## Acceptance criteria

- [ ] `assets/workspace/.github/workflows/release-publish.yml` creates
      `refs/tags/<prefix><version>` as a lightweight ref at the release commit;
      no `git tag -a` remains in the scaffold release chain
- [ ] `tag_already_exists` skip, create-race verification, `TAG_PREFIX`
      composition and **GH013 tombstone diagnosis** all preserved, with
      `tests/test_release_tombstone_detection.py` updated to the API error shape
- [ ] the dead `git_user_name` / `git_user_email` inputs are removed from
      `release-publish.yml` and its call sites, while the scaffold
      `release.yml` rollback identity is left intact
- [ ] `promote-release.yml` and `docs/MIGRATION.md` keep the annotated-tag peel
      as backward compatibility for pre-change consumer tags, with corrected
      wording
- [ ] a workflow-shape test pins the invariant, mirroring
      `tests/test_workflow_release_lightweight_tag.py`
- [ ] verified on the next `devkit-smoke-test` release:
      `gh api repos/vig-os/devkit-smoke-test/git/refs/tags/<tag> --jq '.object.type'`
      reports `commit`, not `tag`

## Notes for triage

`semver:minor` is a judgement call, applied to match
[#1365](https://github.com/vig-os/devkit/issues/1365) (the other change to
stamped consumer workflows). It is behaviourally a backward-compatible bug fix,
so `semver:patch` is defensible if the convention is read as "consumer-visible
managed-file changes are minor only when they add capability" — please override
if so.

Refs: #1370, #1044, #1045, #1157, #1319

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 04:35 PM_

Fixed on dev by PR #1382: the scaffold release-publish.yml now creates the version tag as a lightweight ref via POST /git/refs (mirroring #1370/PR #1374), so consumer release chains no longer contain an unsigned annotated tag object. Preserved: tag_already_exists skip, create-race verification (peeled-then-plain resolution for pre-change annotated tags), TAG_PREFIX composition (#1044), and GH013 tombstone diagnosis (#1319) with the signature re-derived for the REST 422 error shape. Dead git_user_* workflow_call inputs removed; dispatch inputs kept for the rollback job. Live confirmation of the re-derived tombstone signature lands with the next smoke-test release.

