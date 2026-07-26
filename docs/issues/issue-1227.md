---
type: issue
state: closed
created: 2026-07-21T05:32:13Z
updated: 2026-07-21T08:10:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1227
comments: 2
labels: bug, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:41.647Z
---

# [Issue 1227]: [Trunk model: sync-issues direct push collides with require-PR main rulesets](https://github.com/vig-os/devkit/issues/1227)

Found on the first overnight scheduled runs after the trunk switches (2026-07-21). The trunk render correctly points `sync-issues.yml` at `main`, but the sync job commits via direct API push — which a devkit-style "Main protection" ruleset (require PR + required status check) refuses:

```
##[error]Repository rule violations found
Changes must be made through a pull request.
Required status check "CI Summary" is expected.
```

Live failure: vig-os/org-config run of 2026-07-21T05:22Z. Gitflow repos never hit this because sync targets `dev`, whose ruleset admits the bot. Trunk repos without rulesets (vault, exo-fleet) are unaffected by THIS gap (they fail for a different reason: missing exo-pet org secrets).

Options:
- (a) Document (MIGRATION.md trunk section + provisioning checklist): trunk repos with a require-PR main ruleset must add the commit app as a ruleset **bypass actor** — keeps sync semantics identical to gitflow-dev. Cheapest, no code.
- (b) Make the scaffolded sync job workflow-model-aware: on trunk, open a short-lived PR instead of direct push (heavier; auto-merge needs the same checks the sync content can never satisfy → probably needs bypass anyway).

Recommend (a) now, (b) only if bypass-actor proves unacceptable.

Refs: #1205
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 07:06 AM_

Decision (2026-07-21): ruleset **bypass rejected** for security — a bot that can write org-config main can change the applied org configuration. PR-based sync also rejected for v1 (inherent approval toil, ruleset-dependent safety value, stale-PR machinery with zero consumers) and recorded as an ask-gated deliberate exclusion.

Remediation path: **#1228** — `DEVKIT_SYNC_TARGET` + `DEVKIT_SYNC_SCHEDULE` knobs, target 1.4.1. org-config will point sync at a dedicated unprotected mirror branch (weekly cadence); this issue stays open for the MIGRATION.md/provisioning-checklist documentation, which ships with #1228.

Separate finding from the same overnight failures (not this issue): vault + exo-fleet fail earlier, at token generation — the exo-pet org repos lack the `COMMIT_APP_*` repo-level secret declarations in exo-pet/org-config (part-registry has them; vault/exo-fleet entries do not). Fix goes through exo-pet/org-config + a manual apply (Free-plan read-only posture).

---

# [Comment #2]() by [c-vigo]()

_Posted on July 21, 2026 at 08:10 AM_

Remediation shipped: PR #1232 (merged to dev @a1f19748) adds the `DEVKIT_SYNC_TARGET`/`DEVKIT_SYNC_SCHEDULE` knobs and the MIGRATION.md documentation this issue stayed open for — including the no-bypass security rationale and the mirror-branch guidance for trunk repos with require-PR main rulesets. Ships with 1.4.1; org-config gets pointed at `sync/issue-mirror` once released. The separate vault/exo-fleet token-generation finding (missing `COMMIT_APP_*` secret declarations in exo-pet/org-config) remains tracked outside this issue.

