---
type: issue
state: open
created: 2026-09-29T06:10:53Z
updated: 2026-09-29T06:10:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1760
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:49.726Z
---

# [Issue 1760]: [The branch-name rule exists only inline in ci.yml, so every consumer's local gate must duplicate it (and drifts)](https://github.com/vig-os/devkit/issues/1760)

## Problem

The branch-name convention is enforced in exactly one place — the `Validate branch name` step inside the
scaffolded `ci.yml`:

```bash
ALLOWED="^(main|dev)$"
ALLOWED+="|^chore/[a-z0-9]+(-[a-z0-9]+)*$"
ALLOWED+="|^(${TYPES_ALTERNATION})/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$"
ALLOWED+="|^worktree/[0-9]+$"
ALLOWED+="|^renovate/.+$"
ALLOWED+="|^release/[0-9]+\.[0-9]+\.[0-9]+$"
```

It is not exposed in any reusable form — no hook, no script, no `vig-utils` entry point. `grep -rl`
across `assets/` and `packages/` finds it nowhere else.

So a consumer who wants the same rule enforced **at commit time** — which is the only place it can be
enforced usefully, since a CI-only branch-name gate fails after a full CI leg — has to reimplement it,
and the two copies then drift.

## That drift, concretely

vig-os/tessera had a `no-commit-to-branch --pattern` accepting `<type>/<slug>` with **no issue number**,
while `ci.yml` requires `<type>/<issue>-<summary>` for every type but `chore`. A branch therefore passed
every local gate and failed only in CI:

```
##[error]Branch name 'ci/nix-check-timeout-headroom' does not follow the convention
<type>/<issue>-<summary> (types: chore,feat,feature,fix,…)
```

Cost: one wasted ~45-minute CI leg, plus a closed PR — renaming a branch to fix it closes its open PR
rather than following it. Filed downstream as vig-os/tessera#499.

Worth noting the local hook's rationale was *reasonable*: `.gitmessage` already forces `Refs: #<issue>`,
so requiring the number in the branch name too looks redundant. The problem is not that either rule is
wrong — it is that two gates for one convention were written independently and only one of them blocks
merges.

## Suggested fix

Expose the rule once, so a consumer can call it rather than restate it. Any of:

1. **A `vig-utils` entry point**, e.g. `validate-branch-name`, mirroring how `validate-commit-msg` /
   `validate-commit-range` are already shared between the scaffolded pre-commit hook and CI. This is the
   established pattern in this repo and would need no new concepts — the commit-message rule is already
   single-sourced exactly this way, which is why *it* has not drifted.
2. **Ship the pre-commit hook** alongside the CI step, both rendered from `DEVKIT_BRANCH_TYPES` at
   scaffold time, so adopting the scaffold gets both halves.
3. Failing either, **document** in the scaffold that the rule is CI-only and that a consumer adding a
   local gate must mirror the exact clause list — weakest option, since it leaves the duplication and
   only warns about it.

(1) seems clearly right given the precedent: `DEVKIT_BRANCH_TYPES` already feeds CI, so the type list is
single-sourced; it is the *shape* rule that is not, and an entry point would fix that for every consumer
at once.

## Interim, downstream

tessera now has `scripts/check-branch-name.sh`, which mirrors `ALLOWED` clause for clause and reads the
type list from `.vig-os`'s `DEVKIT_BRANCH_TYPES` — so the two gates cannot drift on *which types exist*,
only on the shape, and the script says so at the top. Happy to contribute that upstream as the basis for
(1) or (2) if useful.

Note also that consumers using Dependabot rather than Renovate need a `dependabot/**` clause here, which
is vig-os/devkit#1755 — a second thing a duplicated local gate has to remember to mirror.
