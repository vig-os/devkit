---
type: issue
state: closed
created: 2026-08-17T07:18:23Z
updated: 2026-08-17T09:51:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1530
comments: 2
labels: feature, priority:high, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:15.361Z
---

# [Issue 1530]: [[FEATURE] devkit-upgrade: report a failed upgrade as a tracking issue (no artifact today)](https://github.com/vig-os/devkit/issues/1530)

## Description

When `devkit-upgrade.yml` fails, it leaves **no artifact in the repo at all** —
no branch, no PR, no issue, no comment. The only signal is a red scheduled run
plus GitHub's scheduled-workflow-failure email to whoever last touched the
workflow file, which is exactly the notification everyone filters away.

The branch is created with a local `git switch -c`; the remote ref only appears
in the "Publish the adoption commit via API" step. A failure before that point
(the in-shell commit, the scaffold run, the version resolve) is therefore
completely invisible in-repo. The next scheduled run fails identically and
silently, and the consumer's `DEVKIT_VERSION` stays behind indefinitely.

Observed live: https://github.com/vig-os/org-config/actions/runs/32002045870
failed at the commit step on 2026-08-17. Nothing was left behind; without
someone opening the Actions tab, the repo would have sat on 1.9.0 forever.

## Why this is not a revert of #1405

#1405 removed the per-adoption **issue** on the grounds that, Renovate-style,
the bot PR is the traceable artifact. That reasoning is correct and should
stand — for the **success** path. It has no answer for the failure path, where
by construction there is no artifact. Renovate does not rely on green runs
either: it keeps a Dependency Dashboard issue precisely so failures surface in
the repo rather than in Actions logs.

What is proposed here is a **failure alert**, not an adoption issue: different
trigger, different lifecycle, at most one open at a time per repo.

## Proposed behaviour

- An `if: failure()` step that opens **or updates** a single tracking issue per
  repo, e.g. `chore(devkit): upgrade to <target> failed`, containing the run
  URL, the failing step, and the current vs. target version.
- Re-use the same issue on repeat failures (comment or edit) rather than opening
  a new one weekly.
- Close it automatically on the next successful run, so a fixed upgrade
  self-cleans.
- Requires `permission-issues: write` on the minted App token, alongside the
  existing contents / pull-requests / workflows grants.

## Rejected alternative

**Pushing the half-applied branch on failure.** The commit never happened — the
hooks blocked it — so there is nothing coherent to push, and #1308 exists
precisely so that only API-signed commits leave the runner. A stranded branch
carrying a partial scaffold is worse than no branch.

## Notes

Consider whether the same alert should fire when the resolve step no-ops for an
unexpected reason (malformed pin, missing `DEVKIT_VERSION`) — those exit
non-zero today and would be covered by `failure()` for free.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 07:18 AM_

Triggered by #1529 — that upgrade failed on 2026-08-17 and left nothing behind. See also #1531.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 17, 2026 at 09:51 AM_

Implemented in #1535 (merged to dev). A separate `report` job (`!cancelled() && needs.upgrade.result`-gated) opens or re-uses a single marker-identified tracking issue on failure — run URL, failing step, pinned vs target version — and any fully green run closes it. The Issues grant is a separate best-effort mint, so a missing App grant degrades to a ::warning:: instead of breaking the upgrade. Both org installations of vigos-devkit-upgrade already accept issues:write (verified via API), so no admin action is needed. Ships with 1.11.0; consumers pick it up one train later (cron runs from their base branch).

