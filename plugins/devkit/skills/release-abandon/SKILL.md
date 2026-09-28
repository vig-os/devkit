---
name: release-abandon
description: >-
  Abandon a finalized-but-unpublished vigOS devkit release: run the read-only state lookup, refuse outright when
  the GitHub Release is already published (deleting it would burn the tag name permanently) or when the release PR
  is out of draft, then dispatch the canonical abandon verb and verify the branch, tag, PR and Release are gone and
  the changelog was restored. Use when asked to abandon, drop, cancel or roll back a release train.
argument-hint: "X.Y.Z"
disable-model-invocation: true
---

# devkit release-abandon

The rejection path for a train you no longer want: delete the **draft** Release, delete the tag, close the PR,
delete the release branch, restore `dev`'s `## Unreleased`.

**Draft-only, and the workflow enforces it server-side.** A *published* Release is a different thing entirely:
deleting one tombstones its tag name org-wide and permanently (#1301), so the version can never be re-cut under
that name. That is how the 1.5.0 train became a ghost. Draft Releases never tombstone — deleting a draft is always
safe.

## 1. State lookup

Run `/devkit:status`. You need sections 4 (the branch and PR), 5 (pre-release tags) and 6 (whether a Release object
exists for the bare tag and whether it is a draft).

```bash
gh release view 1.2.3 --json isDraft,isPrerelease,url
gh pr list --state open --base main --json number,headRefName,isDraft,url
git ls-remote --heads origin 'refs/heads/release/1.2.3'
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| The Release for `X.Y.Z` is **published** | Deleting it tombstones the tag name permanently (#1301). The workflow hard-refuses, and so must you | Fix forward: cut the next patch version |
| The release PR is out of draft | Out of draft means it was offered for the approval that promotes it; abandoning behind that is a decision, not a cleanup | Confirm with the operator explicitly, or promote |
| A Release is still attached to the tag after the draft deletion | The workflow refuses to delete a tag that still carries a Release | Read the run log; do not delete the tag by hand |
| Nothing in flight for this version | There is nothing to abandon | `/devkit:status` and re-read what you meant |
| Working tree is dirty | Not fatal here (the workflow acts on remote refs), but the restored `## Unreleased` will land on `dev` and you want a clean local view of that | Commit or set aside first |

## 3. Confirm

There is **no dry-run input** on this workflow. Echo the line, list exactly what will be deleted (branch, tag, PR,
draft Release) and what will be restored (`dev`'s `## Unreleased`), and get an explicit confirmation.

## 4. Dispatch

```bash
just abandon-release 1.2.3
```

The recipe dispatches `abandon-release.yml`. Never delete the tag, branch, PR or Release by hand: the workflow
checks the draft precondition first and refuses the one deletion that cannot be undone.

## 5. Verify

```bash
gh run list --workflow abandon-release.yml --limit 1 --json status,conclusion,url
git ls-remote --heads origin 'refs/heads/release/1.2.3'
git ls-remote --tags origin | sed -n 's#.*refs/tags/##p' | grep -v '\^{}' | grep '^1\.2\.3'
gh release view 1.2.3 --json url || echo "no Release — expected"
```

Confirm all of it is gone and that `dev`'s `## Unreleased` carries the entries back. The workflow fails loudly if
anything is left over; report leftovers verbatim.

## 6. Hand off

`dev` is free again. When the fix is ready → `/devkit:release-prepare` for the same version (the name was never
burnt, because nothing was ever published).
