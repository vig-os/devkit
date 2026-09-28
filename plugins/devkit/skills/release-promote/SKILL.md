---
name: release-promote
description: >-
  Promote a finalized vigOS devkit release: run the read-only state lookup, refuse when the draft Release is
  missing or already published, when the downstream validation gate has not published a final Release, when the
  floating tag would move backwards, or when the PR is unapproved or red, then dispatch the canonical promote verb
  and verify the outcome. Use when asked to promote, publish or ship a finalized release.
argument-hint: "X.Y.Z"
disable-model-invocation: true
---

# devkit release-promote

Phase 6 of the release cycle, and the irreversible one: move the floating tag, publish the draft GitHub Release,
merge the release PR, then clean up the pre-release artifacts. Everything before this is recoverable. This is not.

## 1. State lookup

Run `/devkit:status`. You need sections 6 (the whole promote gate), 4 (the PR's approval and CI state) and 7 (the
hotfix lane, which decides promote order).

```bash
gh release view 1.2.3 --json isDraft,isPrerelease,url
gh pr view --json number,isDraft,reviewDecision,statusCheckRollup,url
gh api repos/vig-os/devkit/releases --paginate \
  --jq '.[] | select(.draft == false and .prerelease == false) | .tag_name'
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| No GitHub Release for the tag | Nothing to promote | `/devkit:release-finalize` |
| The Release is **already published** | Promote has run, or a human published the draft by hand. Re-running cannot un-publish, and deleting it would tombstone the tag name permanently (#1301) | Verify the rest of the promote landed; if not, finish it by hand and record what you did |
| The draft Release for this version was **deleted** | This is the tombstone trap (#1301): the tag name is burnt org-wide and the gate can never pass | Re-cut the content as the next patch version |
| Promoting would move the floating tag **backwards** | The floating tag follows whichever version promoted last; a stale train promoted after a newer one walks it back (#1626). The workflow refuses too | Promote in version order, or abandon the stale train and re-cut as a patch of the newer line |
| **devkit only:** the downstream smoke-test repo has no **published, non-prerelease** Release for the tag | The cross-repo validation gate has not accepted this version; it is `promote-release.yml`'s hard precondition | Wait for the downstream release, or investigate the smoke test |
| The downstream Release is still a draft or still a pre-release | Same gate; acceptance is the published final, nothing less | Wait |
| The release PR is still a draft, unapproved, red, or still running | `main` requires an approving review and green checks; promote merges the PR | Get the approval, fix CI |
| A hotfix is in flight on an older line | Promoting out of order is what walks the floating tag backwards (#1626) | Sequence the two trains deliberately |

There is **no dry-run input** on this workflow. The state lookup above *is* the dry run: read every gate, report
each as pass or fail, and only dispatch when all of them pass.

## 3. Confirm

Echo the line, the version, the current floating-tag holder, and the gate results you just read. Get an explicit
confirmation from the operator. Say plainly that this step is irreversible.

## 4. Dispatch

```bash
just promote-release 1.2.3
```

The recipe dispatches `promote-release.yml`, which re-checks every gate server-side before it publishes anything.

## 5. Verify

```bash
gh run list --workflow promote-release.yml --limit 1 --json status,conclusion,url
gh release view 1.2.3 --json isDraft,url
gh pr list --state merged --base main --limit 5 --json number,headRefName,mergedAt
```

Confirm: the floating tag moved, the Release is published (`isDraft: false`), the release PR merged, and the
pre-release cleanup ran. The cleanup job is best-effort and `continue-on-error`, so check it explicitly and report
leftovers rather than assuming they are gone.

Migrate any consumer still pinned to a pre-release tag **before** the cleanup deletes it.

## 6. Hand off

The train is done. `sync-main-to-dev.yml` opens the PR that carries `main` back to `dev`; merge it before the next
train is cut, or `/devkit:release-prepare` will refuse with "dev is behind main".
