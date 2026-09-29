---
name: release-finalize
description: >-
  Finalize a vigOS devkit release: run the read-only state lookup, refuse when no candidate was ever published,
  when the release PR is still a draft, when CI is red or the tree is dirty, then dispatch the canonical finalize
  verb and stop at the draft GitHub Release — publishing it is the cycle's single human approval. Use when asked to
  finalize or tag a release.
argument-hint: "X.Y.Z"
disable-model-invocation: true
---

# devkit release-finalize

Phase 5 of the release cycle: set the release date in the changelog, build and test, create the final tag, publish
the images, and open a **draft** GitHub Release. Then stop.

**This skill never publishes a Release.** Publishing is the one human approval the cycle collects, and with
immutable releases enabled it is irreversible: a published Release locks its tag, and deleting it later tombstones
the tag name org-wide and permanently (#1301).

## 1. State lookup

Run `/devkit:status`. You need sections 4 (the release PR and its draft state), 5 (pre-release tags — at least one
must exist), 6 (no Release object yet for the bare tag) and 10 (secrets).

```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
gh pr view --json number,isDraft,reviewDecision,statusCheckRollup,url
```

### Validate the version before anything uses it

The `just` recipes interpolate their argument straight into a shell command, so an unvalidated version is a typo
surface and a command-injection surface at once. Check it, and quote `"$VERSION"` at every use afterwards:

```bash
VERSION=1.2.3
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "refusing: '$VERSION' is not X.Y.Z"; exit 1; }
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| No pre-release tag exists for this base version | The workflow requires at least one published candidate before a final; it refuses with "No RC tags found" | `/devkit:release-candidate` |
| The release PR is still a **draft** | Marking it ready is a human act, and it is the final-release gate | Ask the operator to mark it ready; do not do it for them |
| A candidate run is still in progress | Two publishes would race on the same tag and manifest lane | Wait for it, then retry |
| The release PR has failing CI | The final artifact would be built from a tree that does not pass | Fix CI on the release branch |
| Working tree is dirty | The workflow builds the pushed ref, not your tree | Commit and push |
| A **published** Release already exists for `X.Y.Z` | The name is taken and locked; the workflow refuses | Cut the next patch version |
| A **draft** Release already exists for `X.Y.Z` | The finalize already ran | `/devkit:release-promote`, or `/devkit:release-abandon` to drop it |
| `RELEASE_APP_*` / `COMMIT_APP_*` missing | The publish fails partway | Provision the Apps first |

## 3. Dry run first

Echo the line and the observed state, then confirm:

```bash
just finalize-release 1.2.3 "" -f dry-run=true
```

## 4. Dispatch

```bash
just finalize-release 1.2.3
```

The recipe dispatches `release.yml` with `release-kind=final`. A failed run rolls itself back and opens an issue;
recovery is always forward — a new candidate, then a new final — never a retry of a burnt name.

## 5. Verify, then stop

```bash
gh run list --workflow release.yml --limit 1 --json status,conclusion,url
gh release view 1.2.3 --json isDraft,isPrerelease,url
```

Confirm the run succeeded, the tag exists, and a Release exists for it with `isDraft: true`. If `isDraft` is
`false`, something published it — say so loudly and stop; from that point the tag is locked.

Report the Release URL and hand it to the operator with one sentence: the draft is theirs to review. Do not publish
it, do not merge the PR, do not move any floating tag.

## 6. Hand off

Once the downstream gate has accepted the release and the operator has approved the PR → `/devkit:release-promote`,
which publishes the draft, moves the floating tag and merges the PR in the right order. If the release is rejected
while the Release is still a draft → `/devkit:release-abandon`.
