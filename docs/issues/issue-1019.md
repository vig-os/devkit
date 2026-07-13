---
type: issue
state: open
created: 2026-07-13T12:48:05Z
updated: 2026-07-13T12:48:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1019
comments: 0
labels: chore
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:50.755Z
---

# [Issue 1019]: [chore(ci): allowed commit scope list is stale — rejects ~49% of the scopes actually in use](https://github.com/vig-os/devkit/issues/1019)

Surfaced while fixing a stale local `core.hooksPath` during the 1.1.0 release train (PR #1018).

## Problem

`.pre-commit-config.yaml` restricts commit scopes to five values:

```yaml
- id: validate-commit-msg
  stages: [commit-msg]
  args: [
    "--types", "feat,fix,docs,chore,refactor,test,ci,build,revert,style",
    "--scopes", "agent,ci,setup,image,vigutils",
    ...
  ]
```

That list no longer reflects how the repo actually commits. Across all history:

- **1204** commits carry a scope.
- **612** use one of the five allowed scopes (`ci` 385, `image` 97, `setup` 90, `vigutils` 30, `agent` 10).
- **592 (~49%) use a scope the hook would reject today.**

Top rejected scopes, by frequency:

| scope | commits | | scope | commits |
|---|---|---|---|---|
| `workspace` | 74 | | `release` | 19 |
| `nix` | 67 | | `gh-issues` | 19 |
| `security` | 50 | | `actions` | 15 |
| `deps` | 49 | | `pip` | 13 |
| `changelog` | 49 | | `init-workspace` | 13 |
| `worktree` | 28 | | `flake` | 21 |
| `home` | 23 | | `devshell` | 8 |

This is not hypothetical drift — `fix(workspace): point scaffolded flake stub at github:vig-os/devkit` is **already merged into `release/1.1.0`** and passed CI green.

## Why it went unnoticed

Two independent reasons, both worth fixing:

1. **`validate-commit-msg` is a `stages: [commit-msg]` hook**, so it never runs under `pre-commit run --all-files`. CI only runs the file-stage suite, so **CI never validates commit messages** despite `docs/COMMIT_MESSAGE_STANDARD.md` stating "the commit-msg hook (and CI) will reject any commit that does not match this standard".
2. The only thing that *did* enforce it — the local hook — has been **inert**: `core.hooksPath` still pointed at `…/vigOS/devcontainer/.git/hooks`, a path that stopped existing at the `devcontainer` → `devkit` rename. Git silently ran no hooks at all.

With both enforcement paths dead, the scope vocabulary drifted freely for hundreds of commits.

## It would also reject our own automation

`changelog` (49 commits) is the scope used by **`commit-action-bot[bot]`** for automated changelog entries, and `deps`/`pip`/`npm`/`actions` are the Renovate-style dependency scopes. Turning enforcement on as-configured would break the bots before it broke anyone else.

## Suggested fix

Update `--scopes` to the vocabulary actually in use, rather than rewriting ~600 commits to match a list nobody has been able to enforce. Proposed list:

```
agent, ci, image, setup, vigutils, workspace, nix, security, deps,
changelog, worktree, home, flake, release, gh-issues, actions, install,
scripts, skills, docs, test, build
```

Worth deciding alongside it:

- **Consolidate aliases** so the vocabulary stays meaningful: `vig-utils` (5) → `vigutils` (30); `tests`/`testing` (4) → `test`; `container` (2) → `devcontainer` (8); `rfc` (2) → `rfcs` (3).
- **Or drop the allowlist entirely** and validate only the *type* + `Refs:` line, letting scope be free-form lowercase. Given the long tail (58 distinct scopes, 30 of them used ≤5 times), an allowlist may be more ceremony than value — but a curated list does keep the vocabulary from sprawling further.
- **Enforce commit messages in CI**, not just in a local hook, so the next drift is caught even when someone`s `core.hooksPath` is broken. This is arguably the more important half of the fix — a guard that only runs on healthy laptops is not a guard.

## Not in scope

Do not rewrite existing history. The commits are fine; the list is wrong.

Refs: #988
