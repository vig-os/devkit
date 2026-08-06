---
type: issue
state: open
created: 2026-08-05T08:17:12Z
updated: 2026-08-05T08:17:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1347
comments: 0
labels: bug, priority:low, area:workflow, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-06T05:23:25.158Z
---

# [Issue 1347]: [devkit-upgrade: no-diff dispatch strands the adoption issue it created](https://github.com/vig-os/devkit/issues/1347)

## Description

The devkit-upgrade workflow (#1296) creates/reuses the adoption issue **before** running `install.sh --force` — necessarily, since the branch name embeds the issue number and the in-shell commit needs its `Refs:` line. When the upgrade then produces **no diff**, the publish and PR steps are correctly skipped — but the freshly created adoption issue is left open with no PR ever attached, and nothing closes it.

Cron can't reach this state (it no-ops earlier on "current or ahead"), but a `workflow_dispatch` is an unconditional re-bump by design, so any dispatch at the consumer's current version with a clean scaffold strands an issue.

## Live occurrence (2026-08-05, exo-fleet)

Credential probe after provisioning the exo-pet org: dispatch with `version=1.6.0` on a consumer already fully at 1.6.0 (run 30986580730, green). The run created adoption issue exo-pet/exo-fleet#270, found zero diff, skipped publish + PR, and exited successfully — leaving #270 open until closed by hand. This will recur on every credential probe or repair-run against a current consumer.

## Expected

In the no-diff path, the workflow should clean up after itself:

- if it **created** the adoption issue this run: close it with a "no diff at <version>" comment;
- if it **reused** a pre-existing open issue (the mid-train rc1→rc2→final case): leave it open, at most drop a comment — auto-closing a live train issue would be wrong.

The `Find or create the adoption issue` step already knows which branch was taken (`Created` vs `Reusing`); exposing that as a step output is enough for a final cleanup step gated on `proceed && no-diff`.

## Impact

Cosmetic/paper-cut: one stray open issue per no-diff dispatch, discovered only by whoever audits open issues later.

