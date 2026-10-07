---
type: issue
state: open
created: 2026-10-06T23:03:10Z
updated: 2026-10-06T23:03:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1845
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-07T08:29:20.152Z
---

# [Issue 1845]: [AX: post-scaffold friction — uncommitted flake.lock (intent-to-add) breaks stash/rebase, inert .gitignore.project, dead PR-template links, no consumer CLAUDE.md](https://github.com/vig-os/devkit/issues/1845)

## Context

This continues the field report in #1844 and the comment on #1765: the same agent session (Claude Code, devkit 1.18.0, `--mode direnv --workflow trunk`, consumer `exo-pet/MPECT`). Those covered *install*. This issue covers what happened **after** scaffolding, up to the first green PR. Every item below was verified in-session.

## 1. The scaffold doesn't commit `flake.lock`, and the generated lock then breaks `git stash` and `git rebase`

The initial scaffold commit has `flake.nix` but no `flake.lock`. On the first `direnv allow`, nix writes `flake.lock` and registers it as **intent-to-add** (`git add -N`; `git status` shows `new file:` under *not staged*). Then:

- `git stash push -u` → `error: Entry 'flake.lock' not uptodate. Cannot merge.` (the stash silently doesn't happen)
- During a `git rebase`, re-entering the dev shell (needed by #2) regenerates the lock as intent-to-add again, and `rebase --continue` reports `You must edit all merge conflicts` with no conflict markers anywhere.

**Suggestion:** resolve and commit `flake.lock` in the scaffold's initial commit. It pins the dev shell, so it belongs in history anyway, and the intent-to-add state never arises.

## 2. The dev-shell commit guard gives no hint for in-progress operations

`git rebase --continue` from a plain shell → `Please commit your changes within the dev container or the nix dev-shell.` The fix is `GIT_EDITOR=true direnv exec . git rebase --continue`, but the message doesn't say so. Combined with #1, entering the shell mid-rebase changes the tree. **Suggestion:** when `.git/rebase-merge` / `rebase-apply` / `MERGE_HEAD` exists, print the `direnv exec . git <op> --continue` form.

## 3. `.gitignore.project` entries do nothing until the next re-render

Its header says entries are "appended to that regenerated .gitignore", which means an entry added today is **inert until `install.sh --force`**, and that run needs a clean non-main branch (upgrade preflight). The natural move (add `/papers/*.pdf`, commit) silently doesn't ignore anything. I fell back to a nested `papers/.gitignore`. **Suggestion:** a `just sync-gitignore` (or a pre-commit hook) that re-merges `.gitignore.project` into `.gitignore` locally, or a first header line that says plainly "takes effect on the next re-render; for immediate effect use a nested `.gitignore`".

## 4. The downstream PR template links to devkit-internal paths

`.github/pull_request_template.md` as scaffolded into a consumer:

- L57: `I have updated the documentation accordingly (edit \`docs/templates/\`, then run \`just docs\`)`. There is no `docs/templates/` or `just docs` in a consumer.
- L74: `See [commit-messages.mdc](../../rules/commit-messages.mdc)`. This is a dead link in a consumer. `docs/COMMIT_MESSAGE_STANDARD.md` is what's scaffolded.

## 5. A remote whose `main` holds only a bot "Initial commit" needs a hand rebase

Orgs that provision declaratively (otterdog `auto_init: true`) hand you a remote `main` holding one bot commit with a README. The scaffold's own root commit then has to be rebased onto it, with a README add/add conflict, before the first push. **Suggestion:** when `origin/main` exists and contains only a single README-only commit, have init rebase onto it automatically, keeping the scaffold README. Or document the two commands. (The org side is asked to prefer `auto_init: false` in exo-pet/org-config#102.)

## 6. Consumers have no `CLAUDE.md`

The scaffold ships `.claude/skills/` (`branch-naming` etc.) and a dev-shell hook stack, but no `CLAUDE.md`. That's the one file an agent reads regardless of where its session is rooted. The same gap cost time on the org-config side (vig-os/org-config#319 §1, exo-pet/org-config#102 §1). Related: #1765, #927. **Suggestion:** a seeded (consumer-owned) `CLAUDE.md` stub covering dev-shell commits, branch naming, `Refs:` policy, and where the skills live.

## What went smoothly (keep it)

- The pre-commit stack ran cleanly in one pass inside the dev shell, and `branch-name` + `validate commit message` caught nothing because the `branch-naming` skill had already set the right shape.
- `ci.yml` honoured `DEVKIT_CI_RUNNER` on the first PR. `CI Summary` was green within ~3.5 min on the self-hosted runners.
- `sync-issues` worked first time once the org-side secret readers were set.

