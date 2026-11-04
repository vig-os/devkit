---
type: issue
state: open
created: 2026-11-03T10:36:19Z
updated: 2026-11-03T10:36:19Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2004
comments: 0
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:58.154Z
---

# [Issue 2004]: [[FEATURE] Carry GitHub App provisioning: manifests as code, just provision-apps (manifest flow), repo-secret sync for Free-plan private repos, run-based verification](https://github.com/vig-os/devkit/issues/2004)

## Description

devkit's scaffolded workflows depend on three GitHub App identities (`COMMIT_APP_*`, `RELEASE_APP_*`, `DEVKIT_UPGRADE_APP_*`). Their permission sets live only in prose: `docs/runbooks/devkit-upgrade-app.md` covers one App, and the release and commit Apps' grants are spread across issues (e.g. #1850: `checks:read` and `statuses:read`, found by a failing release). Proposal: carry the App provisioning as a devkit recipe that consumers can run.

## Problem Statement

Seen on `exoma-ch/ravmatic` (private repo, Free-plan org, devkit 1.18.0):

- All three Apps are installed on the org for all repos, and `repos/R/actions/organization-secrets` lists all six secrets as available.
- At runtime the org secrets are **empty** (GitHub doesn't deliver org secrets to private repos on Free). The first `devkit-upgrade` dispatch failed: `DEVKIT_UPGRADE_APP_CLIENT_ID / DEVKIT_UPGRADE_APP_PRIVATE_KEY secrets are not configured` (https://github.com/exoma-ch/ravmatic/actions/runs/41620166248). Release and sync-issues would fail the same way, at the first release.
- The fix is repo-level secret copies, which needs the private keys. GitHub never shows a key twice, so each new private repo means either finding where someone saved the PEMs, or an owner clicking "Generate a private key" for each App, by hand.

## Proposed Solution

1. **App manifests as code.** One manifest per role (commit, release, devkit-upgrade) in `assets/apps/*.json`: exact permissions, `events: []`, webhook inactive. That makes the runbooks' permission tables, and fixes like #1850, a reviewed diff rather than prose.
2. **`just provision-apps`.** Runs GitHub's manifest flow: a one-shot local server serves the pre-filled form, catches the redirect `code`, exchanges it via `POST /app-manifests/{code}/conversions` for the App id, client id and PEM, and pipes them to `gh secret set` without logging them. Only the two clicks GitHub requires remain (Create, Install), so the runbooks' "a human creates it" stance holds; the human just no longer retypes permission tables. Prior art: a working implementation of exactly this flow (ephemeral port, random path, PEM never logged).
3. **`just sync-app-secrets <repo>`.** For Free-plan private repos: push repo-level copies from an encrypted store the operator controls (sops/age), so each new private consumer is one command.
4. **Verify by running, not listing.** A `workflow_dispatch` probe that mints each token via `actions/create-github-app-token` and reports which roles work. The secrets-listing API gives a false positive on Free + private (above).

## Related

#1997 (plan-aware scaffold, corrected: org secrets don't reach private repos), #2000 (GitHub-side bootstrap), #1850, #1302, `docs/runbooks/devkit-upgrade-app.md`.

