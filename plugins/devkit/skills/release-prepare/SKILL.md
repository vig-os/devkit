---
name: release-prepare
description: >-
  Cut a vigOS devkit release branch for a version: run the read-only state lookup, refuse on every state that would
  foot-gun the train (another train in flight, hotfix in flight, dirty tree, dev behind main, empty Unreleased,
  existing tag or branch), then dispatch the canonical prepare verb and verify the draft release PR opened. Use when
  asked to start, cut or prepare a release.
argument-hint: "X.Y.Z"
disable-model-invocation: true
---

# devkit release-prepare

Phase 1 of the release cycle: freeze `dev`'s `## Unreleased`, cut `release/X.Y.Z`, reset `Unreleased` on `dev`, and
open a **draft** PR into `main`. The workflow does all of that. This skill's whole job is to refuse before it starts
and to verify afterwards.

`docs/RELEASE_CYCLE.md` is the source of truth for the cycle. Never re-implement any of its steps here.

## 1. State lookup

Run `/devkit:status` and read its report. Do not proceed on a cached or remembered state — re-read it in this run.
You need, at minimum: trains in flight (section 4), hotfix lane (section 7), workflow model and `dev` vs `main`
(section 8), and required secrets (section 10).

Then read the two local facts the report does not cover:

```bash
git status --porcelain
git rev-parse --abbrev-ref HEAD
```

## 2. Refuse

Stop and explain, naming the state you read and the verb that clears it. Never "work around" one of these.

| State | Why | Offer instead |
|---|---|---|
| Any other `release/*` branch exists | Single-train policy (#1627). A train cut alongside another predates its fix, so promoting it later silently reintroduces the regression | `/devkit:release-promote` or `/devkit:release-abandon` on the existing train |
| A hotfix is in flight (a `release/*` cut from `main`) | Same refusal, mirrored (#1627). Promote order would also decide whether `:latest` walks backwards (#1626) | Finish the hotfix first |
| Working tree is dirty | An uncommitted change is invisible to the workflow, which reads the pushed ref. You would ship a tree nobody has | Commit or set the work aside, then retry |
| `dev` is behind `main` | The freeze takes `dev`'s `## Unreleased`; `main`'s landed-but-unshipped entries would be dropped silently | Merge the open `chore/sync-main-to-dev-*` PR, then retry |
| `## Unreleased` is empty | A release that describes nothing | Write the changelog entries first |
| Tag `X.Y.Z` or branch `release/X.Y.Z` already exists | The name is taken; if the tag carries a **published** Release the name is burnt permanently (#1301) | Pick the next version |
| `RELEASE_APP_*` or `COMMIT_APP_*` secrets missing | The train fails partway, after it has already moved refs | Provision the Apps first |
| Version is not `X.Y.Z` | The workflow validates the same pattern and refuses | Correct the argument |

The workflow re-checks all of these server-side. Refusing here is not redundant: it saves a failed run that has
already frozen a changelog, and it gives the operator the reason in one sentence instead of in a job log.

## 3. Dry run first

Echo the exact line you are about to run, together with the state you observed, and get an explicit confirmation.
The workflow has a `dry-run` input that validates without changing anything — prefer it when the operator is
unsure:

```bash
just prepare-release 1.2.3 dev -f dry-run=true
```

## 4. Dispatch

```bash
just prepare-release 1.2.3
```

The recipe dispatches `prepare-release.yml`. Do not call `gh workflow run` directly and do not reimplement the
freeze: the recipe is the canonical verb, and a devkit release changes the workflow underneath it.

## 5. Verify

```bash
gh run list --workflow prepare-release.yml --limit 1 --json status,conclusion,url
git ls-remote --heads origin 'refs/heads/release/1.2.3'
gh pr list --state open --base main --json number,headRefName,isDraft,url
```

Confirm all four: the run succeeded, `release/1.2.3` exists, a **draft** PR into `main` exists for it, and `dev`'s
`## Unreleased` was reset. Report what you verified, not what you expect.

## 6. Hand off

Next is review and testing on the release branch, then `/devkit:release-candidate`. The PR stays a draft until the
candidate has been accepted downstream — marking it ready is a human act and belongs to `/devkit:release-finalize`.
