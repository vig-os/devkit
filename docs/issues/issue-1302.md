---
type: issue
state: open
created: 2026-07-30T09:47:39Z
updated: 2026-07-30T09:47:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1302
comments: 0
labels: feature, priority:high, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T11:51:49.877Z
---

# [Issue 1302]: [feat(workflow): devkit-upgrade must authenticate via a dedicated GitHub App (drop the PAT path)](https://github.com/vig-os/devkit/issues/1302)

## Context

The devkit-upgrade workflow (#1296, unreleased — on `release/1.5.0`) reads a static `DEVKIT_UPGRADE_TOKEN` secret, which in practice forces a fine-grained PAT: App installation tokens live one hour and cannot be stored as secrets. PATs are user-bound, expire, and are single-owner (one per org across vig-os / exoma-ch / exo-pet), all rotated manually.

## Decision

A GitHub App is the **only** supported identity. The template mints a per-run installation token in-workflow — the same `actions/create-github-app-token` pattern devkit's own `prepare-release.yml` already uses:

- Secrets: `DEVKIT_UPGRADE_APP_ID` + `DEVKIT_UPGRADE_APP_PRIVATE_KEY` (org-level secrets cover a whole org's consumers).
- Fail-fast with a clear message when either secret is absent.
- The minted token drives checkout/push, the adoption issue, and the PR (so the PR triggers CI); `DEVKIT_UPGRADE_TOKEN` is removed entirely.

Since #1296 has never shipped, changing the contract now (on the release branch) means 1.5.0 ships App-only with no migration debt.

## App provisioning (documented here as the SSoT)

Dedicated App (do **not** reuse the release/commit App — its private key must stay confined to devkit; the upgrade key gets distributed to consumer orgs):

- Name: `vigos-devkit-upgrade` (must not match the agent blocklist)
- Repository permissions: Contents RW, Pull requests RW, Issues RW, Workflows RW, Metadata R
- Webhook: disabled. Public (so exoma-ch / exo-pet orgs can install it later); installed per org on the consumer repos.

Refs: #1296
