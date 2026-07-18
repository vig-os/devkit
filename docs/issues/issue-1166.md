---
type: issue
state: closed
created: 2026-07-17T08:26:19Z
updated: 2026-07-17T09:15:23Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1166
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:27.569Z
---

# [Issue 1166]: [Provisioning gap: Dependency Graph disabled on new repos breaks the Dependency Review CI gate](https://github.com/vig-os/devkit/issues/1166)

## Observed

During the greenfield devkit 1.3.1 deployment to the public repo `vig-os/org-config` (vig-os/org-config#3), the scaffolded CI's **Dependency Review** check failed out of the box: the org creates new repos with the Dependency Graph disabled (`dependency_graph_enabled_for_new_repositories: false`), so the dependency-graph compare API returns 403.

## Fix applied (manually)

`PUT /repos/vig-os/org-config/vulnerability-alerts` (idempotent) enabled the graph; the check then passed.

## Proposal

Every new public consumer will hit this. Fold it into the consumer onboarding/provisioning path — either a documented step in the onboarding checklist (docs/MIGRATION.md) or an installer/init-workspace preflight note when `ci.yml` (with the dependency-review gate from #1140) is deployed.

Found during the 1.3.1 rollout verification.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 09:15 AM_

Documented on `dev` via #1169 — MIGRATION.md now carries an "Enable the dependency graph on new public consumers" provisioning step (`gh api -X PUT repos/<owner>/<repo>/vulnerability-alerts`, idempotent, mode-agnostic) plus a pointer comment at the failure site in the scaffold `ci.yml` dependency-review job. Ships to consumers on the next devkit release.

