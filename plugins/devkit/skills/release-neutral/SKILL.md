---
name: release-neutral
description: >-
  Land a change on main without cutting a vigOS devkit release: run the read-only state lookup, confirm the change
  is genuinely release-neutral (no consumer-visible asset, no changelog edit, no version bump), open the PR through
  the workflow that authors it, and read the guard's verdict. Use when asked to merge to main without a release,
  or when a change belongs on main but changes nothing a consumer receives.
argument-hint: "<branch> <title> [issue]"
disable-model-invocation: true
---

# devkit release-neutral

The lane for changes that belong on `main` but change nothing a consumer receives: devkit's own CI workflows, its
tests, most docs, and the scan-time registers. Cutting a release for these republishes a functionally identical
artifact and sends every consumer an adoption PR that changes nothing they run.

**This lane exists in devkit only.** It is not part of the consumer scaffold. If `/devkit:status` section 1 says
you are in a consumer repo, stop and say so.

The guard decides release-neutrality by machine proof, not by judgement. Your job is to propose honestly and to
report the verdict as it comes back.

## 1. State lookup

Run `/devkit:status`. You need section 1 (is this devkit), section 4 (a train in flight complicates the merge
order) and section 8 (the model and whether `dev` is behind `main`).

```bash
git fetch origin main dev
git log --oneline origin/main..HEAD
git diff --name-only origin/main...HEAD
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| This is not devkit | The lane is devkit-only; the scaffold does not ship it | A normal train in that repo |
| The diff touches `.vig-os` | It carries `DEVKIT_VERSION` — editing it **is** releasing | Leave the version edit out; it belongs to a real train |
| The diff touches a consumer-visible asset under `assets/workspace/` | A consumer receives it, so the change is not release-neutral | `/devkit:release-prepare` |
| The diff carries a `CHANGELOG.md` edit | The entry is mirrored into the image and leaves `## Unreleased` non-empty on `main`, which both prepare verbs refuse to start on | Keep the changelog edit in a separate commit on `dev` |
| The branch is not already pushed, or is not forked from `main` | The workflow opens a PR for an existing branch; it does not create one | Push the branch off `main` first |
| Working tree is dirty | The workflow reads the pushed ref | Commit and push |

## 3. Confirm

Echo the branch, the PR title (Conventional Commits) and the tracking issue, plus the file list you just read and
why each entry is release-neutral. Get an explicit confirmation.

A human does not author this PR, and that is not ceremony: `main` requires one approving review, GitHub forbids a
PR's author from approving their own, and no App holds bypass. The workflow authors it so the maintainer's approval
is legal (#1676).

## 4. Dispatch

There is no `just` recipe for this lane; the workflow is the canonical verb:

Quote every value. A title is free text — an apostrophe in it (`ci(guard): don't drop the label`) ends a
single-quoted argument and the rest of the title becomes shell words:

```bash
BRANCH="chore/1676-example"
TITLE="ci(guard): example"
ISSUE="1676"
[[ "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo "refusing: suspicious branch name"; exit 1; }
[[ "$ISSUE" =~ ^[0-9]+$ ]] || { echo "refusing: issue must be a number"; exit 1; }
gh workflow run release-neutral-open.yml --ref dev \
  -f "branch=$BRANCH" -f "title=$TITLE" -f "issue=$ISSUE"
```

## 5. Verify

```bash
gh run list --workflow release-neutral-open.yml --limit 1 --json status,conclusion,url
gh pr list --state open --base main --json number,headRefName,labels,url
```

Confirm the PR exists and carries the `release-neutral` label — the label is what activates the guard. Then read
the guard's verdict comment:

```bash
gh run list --workflow release-neutral-guard.yml --limit 3 --json conclusion,url
gh pr view <number> --json comments --jq '.comments[-1].body'
```

Report the verdict gate by gate. If a gate fails, the change is not release-neutral: say which gate and why, and
hand off to `/devkit:release-prepare`. Never remove the label to make the guard stop running.

## 6. Hand off

Approval and merge stay with the maintainer. Do not approve, do not merge, and do not push to the PR after it has
been approved — `main` dismisses stale reviews on push.
