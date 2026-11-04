---
type: issue
state: open
created: 2026-11-03T09:28:09Z
updated: 2026-11-03T13:05:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1997
comments: 2
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:32.956Z
---

# [Issue 1997]: [[FEATURE] Plan-aware scaffold: detect a private repo in a Free org and adapt (scanning, rulesets, auto-merge, dependency review)](https://github.com/vig-os/devkit/issues/1997)

## Description

At scaffold time, detect a **private repo in a Free-plan org** and adapt the scaffold, or at least print one consolidated warning. Today four features break or quietly do nothing in that setting, and each one surfaces separately, late.

## Problem Statement

Found while bootstrapping `exoma-ch/ravmatic` (devkit 1.18.0, private, `exoma-ch` on the Free plan):

| Feature | What happens on Free + private | Found |
|---|---|---|
| `scanning` (`codeql.yml`, `scorecard.yml`) | shipped by default, though `docs/SOLO_ADOPTION.md` calls them "already neutral on private repos": dead weight in every PR's workflow list | at scaffold (`DEVKIT_FEATURES_DISABLED=scanning` set by hand) |
| rulesets | `rules/branches/main` answers 403, so `promote-release` cannot promote (#1851) | first promote |
| auto-merge | `PATCH allow_auto_merge=true` is accepted but the setting stays `false`; `sync-main-to-dev.yml` only warns, so its PR waits for a human | first release |
| dependency review | skipped; SECURITY.md says it blocks PRs (#1913) | never, silently |

Org secrets: they do reach the private repo here. `repos/R/actions/organization-secrets` lists `COMMIT_APP_*`, `RELEASE_APP_*` and `DEVKIT_UPGRADE_APP_*`, and `sync-main-to-dev` succeeded. That is worth checking at scaffold time too, since a missing secret only shows up at the first release.

## Proposed Solution

`init-workspace.sh` / `install.sh` can call `gh api repos/R` (visibility) and `gh api orgs/O` (plan; needs `admin:org` read, so best-effort). When the repo is private on Free:

- default `DEVKIT_FEATURES_DISABLED` to include `scanning` on a fresh install, with a notice;
- print one block listing the remaining limits (no rulesets, so #1851 and #1892 apply; no auto-merge, so the sync PR is merged by hand; no dependency review), with the docs links;
- optionally verify that the App secrets the enabled feature groups need are visible to the repo.

Without `gh` auth, skip silently, exactly as today.

## Related

#1851, #1892, #1913, #1891 (visibility-driven cache profile: the same detection).

---

# [Comment #1]() by [gerchowl]()

_Posted on November 3, 2026 at 10:33 AM_

**Correction (verified after filing):** the org secrets do **not** reach this private repo at runtime. `repos/R/actions/organization-secrets` lists `COMMIT_APP_*`, `RELEASE_APP_*` and `DEVKIT_UPGRADE_APP_*` as available, but a dispatched `devkit-upgrade.yml` (https://github.com/exoma-ch/ravmatic/actions/runs/41620166248) failed with `DEVKIT_UPGRADE_APP_CLIENT_ID / DEVKIT_UPGRADE_APP_PRIVATE_KEY secrets are not configured`. That matches GitHub's Free-plan rule (org secrets aren't available to private repos). The earlier `sync-main-to-dev` success was the early 'dev is up to date' exit, so it never needed a token.

This makes secret visibility the **most important** check for this issue: the listing API gives a false positive, so the only reliable probe is a workflow run. Every App-token feature (the release train, sync-issues, devkit-upgrade) needs **repo-level** secret copies on Free + private. The scaffold should say so up front and point at the runbook.

---

# [Comment #2]() by [gerchowl]()

_Posted on November 3, 2026 at 01:05 PM_

One more Free-plan pitfall, hit for real: with `delete_branch_on_merge=true` (devkit's own setting, which consumers copy), merging any PR whose **head is `dev`** (here a manual `dev` -> `main` promotion, https://github.com/exoma-ch/ravmatic/pull/13) makes GitHub **delete `dev`**. On Team, the dev ruleset exempts it; on Free nothing does. It was restored from `main` and the rule is documented downstream. The plan-aware check should warn about it, or set a `dev` -> `main` promotion helper that always branches first.

