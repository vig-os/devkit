---
type: issue
state: closed
created: 2026-07-21T07:05:55Z
updated: 2026-07-21T08:10:42Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1228
comments: 1
labels: area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:41.144Z
---

# [Issue 1228]: [sync-issues knobs: DEVKIT_SYNC_TARGET + DEVKIT_SYNC_SCHEDULE (target 1.4.1)](https://github.com/vig-os/devkit/issues/1228)

## Problem

Trunk consumers point the scaffolded `sync-issues.yml` at `main` (#1205 render). On a repo with a require-PR main ruleset the bot's direct API push is refused (#1227, live failure on vig-os/org-config 2026-07-21). **Decision recorded: no ruleset bypass for the commit app on main** (security: a bot that writes org-config main can change applied org config).

## Design (Carlos-approved 2026-07-21)

Two optional `.vig-os` keys, scaffold-time realized (schedule triggers cannot take inputs), persisted like `DEVKIT_CI_RUNNER` (#1116-style persist block), loud enum/format guards:

- **`DEVKIT_SYNC_TARGET`** — branch the sync job commits to. Default is workflow-model-aware: `dev` (gitflow) / `main` (trunk), preserving today's behavior byte-for-byte when unset. Consumers with a protected main set a dedicated mirror branch (e.g. `sync/issue-mirror`). The job must bootstrap the branch if absent (from the default branch head). Document: the mirror branch diverges permanently and is never merged back — sync regenerates full state each run.
- **`DEVKIT_SYNC_SCHEDULE`** — cron override for the schedule trigger (default: current daily cron). Validate 5-field cron loudly at scaffold time.

## Deliberate exclusion (ask-gated, docs-recorded)

**PR-based sync mode** — evaluated and deferred: toil is inherent against review-requiring rulesets (human approval per sync), its safety value depends on ruleset state the knob cannot see, and it needs renovate-class stale-PR machinery with zero live consumers. Revisit only when a consumer actually asks for human-gated sync. Record in the same docs section that carries the docs-module v1 exclusions pattern.

## Scope

- Manifest keys + resolution + guards + writeback (init-workspace.sh, install.sh)
- Render into scaffolded `sync-issues.yml` (target + cron), workflow-model-aware default
- Branch bootstrap in the sync job
- Tests: render matrix (workflow model × target/schedule), guards, bats
- Docs: NIX.md/RELEASE_CYCLE or MIGRATION "Workflow models" + provisioning checklist note from #1227
- Consumer follow-up after release: org-config sets `DEVKIT_SYNC_TARGET=sync/issue-mirror` + weekly schedule

Closes the remediation path of #1227. Target release: **1.4.1**.

Refs: #1227
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 08:10 AM_

Implemented by PR #1232, merged to dev @a1f19748 (dev-targeted PRs don't auto-close). `DEVKIT_SYNC_TARGET` + `DEVKIT_SYNC_SCHEDULE` per the approved design: workflow-model-aware defaults preserved byte-for-byte when unset, mirror-branch bootstrap from default-branch head, loud guards (charset allowlist + git ref-format for the branch after a review finding hardened it against YAML/shell injection; 5-field cron check), `.vig-os` writeback à la `DEVKIT_CI_RUNNER`. Docs in new MIGRATION.md sync subsection incl. the ask-gated PR-sync exclusion. Ships with 1.4.1. Consumer follow-up after release: org-config sets `DEVKIT_SYNC_TARGET=sync/issue-mirror` + weekly schedule.

