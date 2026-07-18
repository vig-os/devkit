---
type: issue
state: closed
created: 2026-07-17T12:03:44Z
updated: 2026-07-17T13:00:25Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1182
comments: 1
labels: priority:high, area:ci, area:workflow, effort:large, semver:minor, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:24.962Z
---

# [Issue 1182]: [Managed workflows carry 73 zizmor findings (40 high); consumers must baseline devkit's output](https://github.com/vig-os/devkit/issues/1182)

## Description
Running `zizmor` over the 14 devkit-managed workflows in a freshly scaffolded 1.3.1 repo yields **73 findings (40 high / 32 medium)** across every file. Devkit doesn't audit its generated workflows, so any consumer adopting workflow security linting must maintain a baseline for code it does not own and cannot fix (regenerated on upgrade).

## Evidence (org-config)
- vig-os/org-config `zizmor.yml` (landed in org-config#37): per-audit/per-file baseline of exactly those findings, with the explicit rule that repo-authored workflows never inherit an exemption. A devkit upgrade that adds workflows/audits surfaces as new findings to triage — noisy for every consumer.

## Suggested direction
Audit the managed workflows and fix what's fixable (unpinned actions, template-injection surfaces, credential persistence, etc.); ship a maintained devkit-owned baseline for the intentional remainder so consumer baselines shrink to zero.

Refs: vig-os/org-config#15
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 01:00 PM_

Done on dev via PR #1185 (merge @c8192bdc): 8 findings fixed upstream (7 artipacked persist-credentials, 1 template-injection), 65 intentional findings baselined in a devkit-owned zizmor.yml (basename-scoped, scaffolded to consumers via the manifest), and devkit CI now gates the managed workflow set with zizmor 1.25.2. Policy in docs/WORKFLOW_SECURITY.md. Consumer baselines for devkit output shrink to zero from the next release.

