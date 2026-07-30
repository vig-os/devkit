---
type: issue
state: open
created: 2026-07-30T09:47:39Z
updated: 2026-07-30T15:45:46Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1302
comments: 2
labels: feature, priority:high, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T17:15:04.387Z
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
---

# [Comment #1]() by [c-vigo]()

_Posted on July 30, 2026 at 02:34 PM_

Provisioning addendum (live-proven 2026-07-30): consumers' **Signed commits** ruleset must grant the App (`vigos-devkit-upgrade`, id 4434545) a bypass (`bypass_mode: always`) — the workflow's in-shell worktree commit cannot be API-signed without losing hook fidelity. Applied by hand to devkit-smoke-test; fleet-wide rollout tracked in vig-os/org-config#81. With the bypass in place the full path is live-proven end to end: fail-fast → App token mint → adoption-issue reuse (devkit-smoke-test#310) → `install.sh --force` (docker-pinned, #1305) → in-shell commit → push → adoption PR devkit-smoke-test#316 opened by the App with CI triggering.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 30, 2026 at 03:45 PM_

Correction to the provisioning addendum above (maintainer review): ruleset bypasses are **not** part of the provisioning model — verified signatures on protected branches are policy. The interim bypass on devkit-smoke-test is reverted and org-config#81 closed as superseded. The workflow will publish verified App-signed commits via API tree replay instead: #1308. Evidence standing from the live runs: every leg except the final publish is proven (fail-fast, mint, issue reuse, docker-pinned install with real diff, in-shell commit, PR mechanics); the publish leg's live proof lands with #1308.

