---
type: issue
state: closed
created: 2026-07-14T07:28:14Z
updated: 2026-07-14T08:03:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1031
comments: 1
labels: chore, priority:medium, area:workspace, effort:small, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:32.403Z
---

# [Issue 1031]: [chore(workspace): scaffold check-agent-identity — consumers guard AI messages but not AI authors](https://github.com/vig-os/devkit/issues/1031)

Surfaced while closing the scaffold's commit-validation gap in #1026 (Refs: #1019, #163).

## Problem

The AI-agent identity guard (#163) is a three-hook pipeline. After #1026, only two of the three reach consumers:

| hook | stage | runner | scaffold |
|---|---|---|---|
| `prepare-commit-msg-strip-trailers` | `prepare-commit-msg` | ✅ | ✅ (added in #1026) |
| `validate-commit-msg` (blocklist gate) | `commit-msg` | ✅ | ✅ (added in #1026) |
| **`check-agent-identity`** | pre-commit | ✅ | ❌ **missing** |

The first two guard the commit **message**. `check-agent-identity` guards the commit **author/committer** — a different attack surface, and the only one that catches `git commit --author="Claude <...>"`.

## The inconsistent guarantee

A scaffolded repo now *rejects an AI-attributed commit message* while *happily accepting an AI-authored commit*. That is worse than either extreme, because it looks covered:

- `docs/COMMIT_MESSAGE_STANDARD.md` (scaffolded) says *"Never set git author/committer to an AI agent identity. The pre-commit hooks will reject violations."*
- In a consumer repo, no hook does.

This is the same failure shape as #1019 itself — a documented guarantee with no mechanism behind it. Consumers are the ones who'd never notice.

## Suggested fix

Add `scaffold = true;` to the `check-agent-identity` hook definition in `nix/hooks.nix` (the SSoT — both `.pre-commit-config.yaml` renders derive from it; drift is gated by `tests/test_flake_hooks.py`), and re-render `assets/workspace/.pre-commit-config.yaml`.

`.github/agent-blocklist.toml` is already manifest-synced into the scaffold, so the blocklist the hook reads is present in consumer repos — no extra wiring needed.

Worth deciding alongside it:

- **`check-pr-agent-fingerprints` is dead code.** The `vig-utils` entry point exists (`packages/vig-utils/pyproject.toml`) but is not referenced by **any** workflow — devkit's or the scaffold's. Either wire it into the `commit-checks` job (a natural home now that one exists) or drop it. A guard that nothing calls is not a guard.
- The local `check-agent-identity` hook is pre-commit-stage, so unlike `validate-commit-msg` it *does* run under `prek run --all-files` — meaning it is already enforced in the scaffold's `lint` job **if** it is in the config. Scaffolding it therefore buys both local and CI enforcement in one change.

## Why it wasn't bundled into #1026

Scope discipline: #1019 was about commit *messages*. Author identity is #163's concern, and bundling it would have made an already-broad PR untraceable to one issue.

Refs: #163

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:03 AM_

Implemented in #1032 (merged to dev): `check-agent-identity` is now scaffolded. The `check-pr-agent-fingerprints` dead-code question is recorded in the PR description — its only unique coverage post-#1026 is the PR body.

