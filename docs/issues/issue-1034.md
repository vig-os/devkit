---
type: issue
state: closed
created: 2026-07-14T07:59:15Z
updated: 2026-07-14T08:36:27Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1034
comments: 1
labels: bug, priority:high, area:ci, area:workflow, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:31.958Z
---

# [Issue 1034]: [[BUG] sync-main-to-dev checks out dev, then runs a local action that only exists on main](https://github.com/vig-os/devkit/issues/1034)

## Description

The `sync` job in the scaffolded `sync-main-to-dev.yml` checks out `dev`, then
invokes a **local** composite action that may only exist on `main`:

```yaml
      - name: Checkout dev
        uses: actions/checkout@…  # v7.0.0
        with:
          ref: dev               # ← workspace is now dev's tree
          fetch-depth: 0
          token: ${{ steps.commit-app-token.outputs.token }}

      - name: Set up devkit toolchain
        uses: ./.github/actions/setup-devkit-toolchain   # ← resolved from dev's tree
```

GitHub resolves `uses: ./…` against the **checked-out workspace**, not the
workflow's ref. So the moment `main` introduces (or moves) a local action that
`dev` does not yet have, the sync job dies on its first run.

This is a **bootstrap deadlock**: the only thing that would carry the new action
onto `dev` is the very sync PR this workflow can no longer open. It has to be
broken by hand.

Affects two files on `main`:

- `assets/workspace/.github/workflows/sync-main-to-dev.yml` (the scaffold shipped
  to every consumer) — `Checkout dev` at :150, `./.github/actions/setup-devkit-toolchain` at :158
- `.github/workflows/sync-main-to-dev.yml` (the devkit's own) — same pattern at
  :110 / :118, with `./.github/actions/setup-env`

The devkit's own copy has not fired only because `setup-env` has been on its `dev`
for a while; the latent defect is identical.

## Steps to Reproduce

Observed in `vig-os/commit-action` when adopting devkit 1.1.0 (direnv):

1. Land a PR on `main` that adds `.github/actions/setup-devkit-toolchain`
   (i.e. the devkit 1.1.0 scaffold adoption — `vig-os/commit-action#32`).
2. The push to `main` triggers `Sync main to dev`.
3. `resolve-toolchain` ✓ and `check` ✓ pass — both check out the **default** ref
   (`main`), where the action exists.
4. `sync` fails at `Set up devkit toolchain`.

Failing run: https://github.com/vig-os/commit-action/actions/runs/29314999211

Consumer's copy is the scaffold template **verbatim** (`diff` is empty), so this
is not local drift.

## Expected Behavior

The sync job runs to completion and opens the `chore/sync-main-to-dev-*` PR,
regardless of whether `dev` has caught up with `main`'s local actions.

## Actual Behavior

The job fails at `Set up devkit toolchain`:

```
Can't find 'action.yml', 'action.yaml' or 'Dockerfile' under
'/home/runner/work/commit-action/commit-action/.github/actions/setup-devkit-toolchain'.
Did you forget to run actions/checkout before running your local action?
```

`.github/actions/` exists on `main` and is absent on `dev`:

```console
$ git ls-tree origin/main .github/actions/
040000 tree …    .github/actions/resolve-toolchain
040000 tree …    .github/actions/setup-devkit-toolchain
$ git ls-tree origin/dev .github/actions/
(empty)
```

## Environment

- **Consumer**: `vig-os/commit-action` (TypeScript action; `npm` + `tsc` + `ncc`)
- **Devkit version**: 1.1.0 (`DEVKIT_VERSION=1.1.0`)
- **Delivery mode**: `direnv` (`DEVKIT_MODE=direnv`)
- **Runner**: `ubuntu-24.04`
- **Architecture**: AMD64

## Possible Solution

Drop `ref: dev` from the sync job's checkout so the workspace is the triggering
`main` SHA, where the local action is guaranteed to exist:

```diff
       - name: Checkout dev          # → rename: Checkout repository
         uses: actions/checkout@…  # v7.0.0
         with:
-          ref: dev
           fetch-depth: 0
           token: ${{ steps.commit-app-token.outputs.token }}
```

Nothing downstream depends on dev's **working tree**. Every subsequent step
operates on remote refs or the API:

- `Re-check if dev is still behind main` → `git fetch origin main dev`, then
  `git rev-list --count origin/main ^origin/dev`
- `Detect merge conflicts` → `git merge-tree --write-tree origin/dev origin/main`
- `Create sync branch from main` → `git checkout -b "${SYNC_BRANCH}" origin/main`
- `Check for existing open sync PR` / `Clean up stale sync branches` / `Create PR`
  → `gh` against the API

`fetch-depth: 0` and the commit-app token stay as-is, so the merge-base and push
behavior are unchanged. Checking out `main` instead of `dev` is behavior-preserving
for all of them, and makes the job build against the **newer** tree — the one whose
actions it references.

Worth fixing in both copies, and worth a scaffold-lint rule: *a job that checks out
a non-default ref must not `uses: ./…`* — this class of failure will recur every
time a local action is added or renamed.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:36 AM_

Fixed in #1037 (merged to dev): the sync job now checks out the triggering main SHA (dropped `ref: dev`) in both the devkit and scaffold copies, so local composite actions always resolve. Follow-up candidate (not filed yet): a scaffold-lint rule that a job checking out a non-default ref must not `uses: ./...`.

