---
type: issue
state: open
created: 2026-11-08T02:40:39Z
updated: 2026-11-08T02:40:39Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2061
comments: 0
labels: feature, area:workflow, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-08T08:50:21.234Z
---

# [Issue 2061]: [Org control repo: one place for App keys; fleet upgrade and secret sync with per-run, per-repo scoped tokens](https://github.com/vig-os/devkit/issues/2061)

## Problem

Every consumer that runs `devkit-upgrade` (and the release workflows) needs GitHub App credentials in its own Actions secrets: `DEVKIT_UPGRADE_APP_*`, `COMMIT_APP_*`, `RELEASE_APP_*`.

- **GitHub Free:** organization-level secrets and variables are not accessible to private repositories. Each private consumer therefore needs its own copy of every App key. In a real org with ten private consumers, that is ten copies of each key.
- **Copying is manual and risky.** Secret values cannot be read back through the API, and GitHub has no API to mint an App private key, so each copy needs a freshly generated key or a plaintext handover.
- **Blast radius multiplies.** Anyone who can push a workflow to any one consumer can exfiltrate the key. They then hold the App's permissions (contents, workflows, pull-requests write) on **every** repo the App is installed on, permanently.
- **Standing rights.** The credentials sit in N repos all the time, although they are needed only for minutes per run.

## Proposal: an org control repo template shipped by devkit

devkit ships a template (scaffolded like a consumer; site-agnostic) for a private per-org **control repo**:

1. **Key custody.** The App private keys live as repo secrets in the control repo **only**. Repo-level secrets work on every plan.
2. **Fleet upgrade.** A scheduled/dispatched workflow discovers consumers (repos with `.vig-os` / `devkit-upgrade.yml` among the App's installation repos). For each consumer it mints an installation token with `actions/create-github-app-token`, narrowed with `repositories: <that repo>` and `permission-*:`. It then runs the adoption for that repo and opens the PR. Consumers no longer need the upgrade App secrets at all.
3. **Secret sync, only where a consumer truly needs a credential at runtime** (e.g. the release Apps). A separate minimal "provisioner" App has only `secrets: write`. Its per-run token is narrowed per repo and writes the values (`gh secret set -R`) to selected repos. The source values stay in the control repo.
4. **No standing elevated rights.** Agents and humans only *trigger* (`gh workflow run` or `just fleet-upgrade` / `just fleet-sync-secrets` in the control repo). Privileged tokens exist only inside the job, for at most an hour, scoped to one repo and the minimum permissions. Every action is in the Actions log.
5. **Bootstrap.** App creation stays a one-time manual step (GitHub requires the browser clicks). Its credential sink is the control repo, not each consumer.

## Design questions to settle in the RFC

- Run the adoption inside the control repo (cross-repo checkout and push with the scoped token), or `workflow_dispatch` the consumer's own `devkit-upgrade.yml` with a short-lived token input?
- Discovery: the installation repo list plus a `.vig-os` probe, or an explicit allowlist file in the control repo?
- Secret-sync drift detection, given values can't be read back: a rotation timestamp per target?
- Migration for consumers that already hold per-repo App secrets: delete after the first successful fleet run.
- How the WORKFLOW_SECURITY.md App/token model changes.

## Acceptance

An RFC under `docs/rfcs/`, then a template plus docs. A private consumer on a Free-plan org can be upgraded and released with **no** App private key stored in the consumer.
