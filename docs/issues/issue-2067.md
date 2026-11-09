---
type: issue
state: open
created: 2026-11-09T07:15:51Z
updated: 2026-11-09T07:15:51Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2067
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-09T09:33:48.623Z
---

# [Issue 2067]: [Sign off (DCO) the commits managed workflows create via commit-action](https://github.com/vig-os/devkit/issues/2067)

## Need

Consumers that enforce DCO (an author-matching `Signed-off-by:` trailer on every new commit in a PR) cannot sign off the commits devkit's managed workflows create through `vig-os/commit-action`. The commit message comes from the `COMMIT_MESSAGE` env in the managed workflow, and the action has no input for extra trailers, so a consumer can only fix it by editing a managed file (lost on upgrade).

Affected commits (devkit-managed workflows, commit-action v0.3.3):

- `prepare-release.yml`: `chore: freeze changelog for release X` (to `dev`) and `chore: rollback failed prepare-release X` (to `dev`)
- `release-core.yml`: `chore: finalize release X` (to `release/X`). This one is new to both `main` and `dev`, so a DCO check on the release PR fails on it.
- `prepare-hotfix.yml`: the hotfix changelog seed commit (to `release/X`)
- `sync-main-to-dev.yml`: the conflict auto-resolve commit (to the sync branch)

## Ask

One of:

1. commit-action appends `Signed-off-by: <author name> <author email>` of the identity the commit is authored as (opt-in input such as `SIGNOFF: "true"`), and the managed workflows enable it through a `.vig-os` key; or
2. the managed workflows add the trailer to `COMMIT_MESSAGE` themselves, behind a `.vig-os` key (e.g. `DEVKIT_DCO_SIGNOFF=true`).

The trailer must name the commit's **author** identity exactly (DCO checks compare against `%an <%ae>`).

## Context

gerchowl/nodd#84: nodd's `tools/check_dco.py` skips commits already on the integration base (release PRs skip `origin/dev`, sync PRs skip `origin/main`), so the freeze commit is no longer checked; the finalize commit and the sync auto-resolve commit still are, and fail until they carry a sign-off. nodd accepts nothing extra for bot commits.

