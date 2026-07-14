---
type: issue
state: closed
created: 2026-07-14T07:27:43Z
updated: 2026-07-14T08:03:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1030
comments: 1
labels: chore, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:32.807Z
---

# [Issue 1030]: [chore(ci): decide whether 'perf' is an approved commit type](https://github.com/vig-os/devkit/issues/1030)

Surfaced while enabling CI commit-message validation in #1026 (Refs: #1019).

## Problem

`perf` is not in the approved commit-type list, but it is already in our history:

```
b91d7823 perf(image): bake placeholder manifest into the Nix image
```

#1019 established that the *scope* vocabulary had drifted (~49% of scopes were unenforceable). Running the new `validate-commit-range` over a 150-commit slice of `dev` shows the **type** vocabulary has drifted too — just far less. `perf` is the only offender, once.

## Why it matters now

Before #1026 this was inert: nothing validated commit messages, so `perf` sailed through. Now the `commit-checks` job is live, so the next person who reaches for `perf` gets a red build:

```
Unknown commit type 'perf'. Allowed types: build, chore, ci, docs, feat, fix,
refactor, revert, style, test
```

That is a *correct* rejection under the current config — the question is whether the config is right. Someone already reached for `perf` naturally, and it is a standard [Conventional Commits](https://www.conventionalcommits.org/) type, which suggests the list is what's wrong, not the author.

Note the existing commit is **not** a problem: `commit-checks` only validates the commits a PR adds, never history. This is purely about what we allow going forward.

## Decision needed

**Option A — add `perf` (suggested).** One-line change to the `--types` list in `nix/hooks.nix` (the SSoT; both `.pre-commit-config.yaml` renders follow, drift-gated by `tests/test_flake_hooks.py`), plus a row in the type table in `docs/COMMIT_MESSAGE_STANDARD.md`. Matches Conventional Commits and matches what a contributor already assumed.

**Option B — leave it rejected.** `perf` changes are arguably `refactor` or `fix`. Keeping the list small keeps the changelog categories crisp. The hook now teaches this, so the cost is one confused contributor, once.

Either way the outcome should be *deliberate* — right now it is an accident of a list nobody could enforce.

## Not in scope

Do not rewrite the existing `perf(image)` commit. Same rule as #1019: the commit is fine, the list may be wrong.

Refs: #1019

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:03 AM_

Implemented in #1032 (merged to dev): `perf` added to the approved types (Option A) across the SSoT and all renders/docs.

