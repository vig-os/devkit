---
name: release-hotfix
description: >-
  Cut a vigOS devkit hotfix release branch from main: run the read-only state lookup, refuse when any regular train
  is in flight, when the version is not the next patch of the latest tag on main, when the tree is dirty or when
  the repo runs the trunk model (where the lane is redundant), then dispatch the canonical hotfix verb and hand off
  to the candidate and finalize skills. Use when asked for an urgent patch that must not carry dev's pending work.
argument-hint: "X.Y.Z"
disable-model-invocation: true
---

# devkit release-hotfix

The emergency lane: a patch cut from `main` instead of `dev`, so it ships without `dev`'s pending work. Every phase
after preparation is identical to a regular train.

## 1. State lookup

Run `/devkit:status`. You need sections 4 (trains in flight), 7 (hotfix lane), 8 (workflow model) and 10 (secrets).

```bash
git fetch origin main
git describe --tags --abbrev=0 origin/main
git status --porcelain
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| Any `release/*` branch exists | Single-train policy (#1627), the mirror of the refusal `/devkit:release-prepare` applies. A hotfix cannot be cut alongside a regular train | Promote or abandon that train first |
| The version is not the next patch of the latest tag reachable from `main` | The workflow validates exactly this and refuses | Compute the next patch and retry |
| No stable `X.Y.Z` tag is reachable from `main` | There is nothing to hotfix yet | Run a normal train |
| `DEVKIT_WORKFLOW=trunk` | Trunk releases already cut from `main`, so the lane is redundant and is copy-excluded from a trunk scaffold (#1625) — the workflow file may not even be present | `/devkit:release-prepare` |
| Working tree is dirty | The workflow reads the pushed ref; local edits are invisible to it | Commit and push |
| Tag `X.Y.Z` or branch `release/X.Y.Z` exists | The name is taken; if a published Release holds it, it is burnt permanently (#1301) | Pick the next patch |
| `RELEASE_APP_*` / `COMMIT_APP_*` missing | The lane fails partway | Provision the Apps first |

## 3. Dry run first

```bash
just prepare-hotfix 1.2.4 "" -f dry-run=true
```

## 4. Dispatch

```bash
just prepare-hotfix 1.2.4
```

The recipe dispatches `prepare-hotfix.yml`. The `ref` argument only selects **which copy of the workflow file
runs** (`dev` by default) — the workflow checks out `main` itself. Do not pass `main` expecting it to change what
is cut.

## 5. Verify

```bash
gh run list --workflow prepare-hotfix.yml --limit 1 --json status,conclusion,url
git ls-remote --heads origin 'refs/heads/release/1.2.4'
gh pr list --state open --base main --json number,headRefName,isDraft,url
```

Confirm a seeded changelog section exists and a draft PR into `main` is open. To confirm the branch was cut from
`main`, use the run you just dispatched as the evidence — not an ancestry test, which is not conclusive here (the
regular lane pushes an `Unreleased` reset to `dev` immediately after cutting, so `dev`'s tip is not an ancestor of
a branch cut from `dev` either):

```bash
gh run view --log --job "$(gh run list --workflow prepare-hotfix.yml --limit 1 --json databaseId --jq '.[0].databaseId')" 2>/dev/null | grep -i 'checkout main' | head -3
git diff --stat origin/main...origin/release/1.2.4
```

A branch cut from `main` differs from `main` by the seed commit alone. If that diff carries `dev`'s unshipped work,
the wrong lane ran — stop and say so.

## 6. Hand off

Identical to a regular train from here: `/devkit:release-candidate`, then `/devkit:release-finalize`, then
`/devkit:release-promote`. Watch the promote order — a hotfix promoted after a newer train walks the floating tag
backwards, and the promote guard will refuse it (#1626).
