---
type: issue
state: closed
created: 2026-09-29T14:02:35Z
updated: 2026-09-30T17:40:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1767
comments: 1
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-01T08:40:56.992Z
---

# [Issue 1767]: [[FEATURE] Issue-less branch form for every Refs-optional commit type, not just chore](https://github.com/vig-os/devkit/issues/1767)

### Description

`DEVKIT_REFS_OPTIONAL_TYPES` (#1633) lets a consumer name the commit types that may omit `Refs:`, but the branch guard has no matching knob. `chore/<summary>` is the only issue-less branch form, and it is hardcoded: the local `no-commit-to-branch` pattern and CI's branch-name gate both say "never knob-driven". `DEVKIT_BRANCH_TYPES` (#1432) governs only the issue-numbered `<type>/<issue>-<summary>` set.

So a consumer can make `docs` commits issue-less, but not a `docs` branch. The only way to land those commits without an issue is a `chore/<summary>` branch, which mislabels the change.

### Problem Statement

Some consumers are document stores, not code repos. Filing an externally received document (a vendor quotation, a datasheet, an order confirmation) is a routine `docs` change: the document *is* the change, and an issue adds nothing except a duplicate of the PR body. #1633 covers the commit half of that workflow. The branch half is missing, and it cannot be patched locally, because CI re-derives the allowed branch set from `.vig-os` in `resolve-toolchain`.

### Proposed Solution

Let each type in the resolved Refs-optional set also get an issue-less branch form `<type>/<summary>`, the way `chore` already does. That generalises the existing `chore` special case:

- `chore` stays exempt by default. Today's `chore/<summary>` clause becomes the default case of the rule, so existing consumers see no change.
- A consumer with `DEVKIT_REFS_OPTIONAL_TYPES=chore,docs` gets `docs/<summary>` alongside `docs/<issue>-<summary>`.
- The rule is rendered into the same places as today: the local hook pattern, the flake-generated hook and `resolve-toolchain`'s branch output. Local and CI stay in lockstep.

For a type that is Refs-optional but not in `DEVKIT_BRANCH_TYPES`, only the issue-less form is allowed. That is exactly how `chore` behaves now.

### Alternatives Considered

- **A separate `DEVKIT_ISSUELESS_BRANCH_TYPES` key.** More flexible, but it creates a second list that can disagree with the Refs set. A branch that may skip the issue while its commits must still cite one is a contradiction. Deriving the branch rule from the Refs set rules that out by construction.
- **Using `chore/<summary>` for these changes.** Works today, but the branch type and the commit type then disagree, and the history loses the `docs` classification.

### Additional Context

Follow-up to #1633 and #1432.

### Impact

Opt-in only. The default Refs-optional set is `chore`, so the rendered branch pattern for existing consumers is byte-identical.

### Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on September 30, 2026 at 05:40 PM_

Shipped to `dev` in #1790 (4c49e414); reaches `main` with the next release train. Every resolved Refs-optional type now gets the issue-less `<type>/<summary>` branch form across the scaffolded guard, the flake-generated guard and CI's branch-name gate; `chore` stays allowed under every policy.

