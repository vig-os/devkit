---
type: issue
state: open
created: 2026-07-30T15:45:32Z
updated: 2026-07-30T16:12:16Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1308
comments: 0
labels: feature, priority:high, area:workflow, effort:medium, semver:minor
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T17:15:04.025Z
---

# [Issue 1308]: [feat(workflow): devkit-upgrade must publish verified commits (API tree replay, commit-app pattern)](https://github.com/vig-os/devkit/issues/1308)

## Problem

The devkit-upgrade workflow's adoption commit is a worktree `git commit` (by design — inside `nix develop` so consumer hooks run: dist rebuilds, trailer strip, validate-commit-msg). That commit is unsigned, and consumers' **Signed commits** ruleset rightfully rejects it at push (first observed: devkit-smoke-test run 30551310266 / PR #316, closed unmerged). Bypassing the rule for the App was evaluated and rejected by the maintainer: verified signatures on `dev`/`main` are policy — this is exactly what the commit-app pattern exists for.

## Fix

Keep the in-shell commit for **hook fidelity**, then replay the result as a **verified commit** via the GitHub API using the upgrade App's token (GraphQL `createCommitOnBranch` — API commits are GitHub-signed as the App; same pattern as vig-os/commit-action):

1. `install.sh --force` + excluded-path reset (unchanged).
2. `nix develop -c git commit` locally — hooks run, files mutate, message validates. This commit is a **staging artifact, never pushed**.
3. Create the remote branch and replay the commit's tree + message via `createCommitOnBranch` with the App token → verified `vigos-devkit-upgrade[bot]` commit.
4. `gh pr create` as today.

Force-update semantics within a train (rc→rc→final) carry over: the API path recreates the branch head each run.

Consequences: no ruleset bypasses anywhere (the interim bypass on devkit-smoke-test has been reverted); vig-os/org-config#81's fleet-wide bypass rollout is superseded. The merging human's signature status is irrelevant since all incoming commits are verified.

Live proof pending this fix: the push/publish leg of the upgrade workflow (everything else is proven — see vig-os/devkit#1302 evidence trail).

Refs: #1296, #1302, #1305
