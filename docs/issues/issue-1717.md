---
type: issue
state: closed
created: 2026-09-25T15:55:22Z
updated: 2026-09-25T20:25:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1717
comments: 3
labels: chore, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:40.254Z
---

# [Issue 1717]: [[CHORE] Insert the shellcheck-composite-actions hook into existing consumer configs on upgrade](https://github.com/vig-os/devkit/issues/1717)

### Chore Type

CI / Build change

### Description

#1704 adds the scaffolded `shellcheck-composite-actions` pre-commit hook. New scaffolds receive it through `assets/workspace/.pre-commit-config.yaml`, but that file is a **preserved** file on upgrade, so an existing consumer only receives a new hook when `inserted_hook_blocks()` in `assets/init-workspace.sh` lists it (`'<since-version> <hook_id> <feature-group>'`, currently the single `1.16.0 actionlint actionlint` row from #1660).

No row was added in #1704 on purpose: the row needs the version of the release that first ships the hook, that version is not yet fixed (no milestone is open), and a wrong number breaks on a train rename (the #1660 lesson). Until the row exists, existing consumers keep running without the hook while their own composites (the scaffold's `resolve-toolchain` and `setup-devkit-toolchain`, plus anything consumer-authored) stay unlinted.

### Acceptance Criteria

- [ ] `inserted_hook_blocks()` carries a row for `shellcheck-composite-actions` with the version of the first release that ships it, once that version is known (i.e. on the release branch of the next train, or right after the version is fixed)
- [ ] The hook has no feature group; confirm the insertion path handles an ungated hook (the actionlint row is gated on the `actionlint` group) or add the minimal support
- [ ] The existing BATS coverage for hook insertion (#1660) is extended with this row: a consumer config below the version gains the block on upgrade, a config at or above it does not get a duplicate

### Implementation Notes

Do it on the release branch or immediately after `prepare-release` fixes the version, never speculatively on `dev`.

### Related Issues

- #1704 (the hook), #1660 (the insertion mechanism and the rename trap)

### Priority

Medium

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 05:00 PM_

## Triage 2026-09-25: do it on the release branch, nothing to change on `dev` now

Read end to end: `inserted_hook_blocks()` rows are `'<first release shipping it> <hook id> <feature group>'`, and the consumer (`insert_missing_hook_blocks`) reads them with `read -r ver hook feat`, so a **two-field row is legal** and an empty group simply never gates — acceptance criterion 2 needs no code. The block text comes from the rendered template by structural lookup (the `- repo:` entry holding `- id: <hook>`), with `# >>> devkit:` sentinels only as a preference, so the un-sentinelled block from #1718 is fine. Coverage is pytest (`tests/test_scaffold_preserved_hooks.py`, `ACTIONLINT_SINCE`, boundary tests), not BATS — criterion 3 should say so.

The gate is strictly `previous DEVKIT_VERSION < since-version`: too high only under-inserts, too low re-adds a hook a consumer deliberately deleted (the #1651 defect), and nothing ties the literal to the version actually released — trains have been renamed mid-flight twice. A release-time placeholder would need a new stamping seam plus a fail-closed guard (an unsubstituted token makes `version_lt` fail silently), disproportionate for one row; presence-based insertion contradicts the documented invariant. So: **option (b)**. On `release/X.Y.Z`, append `'X.Y.Z shellcheck-composite-actions'` **after** the actionlint row (the insertion anchors on `actionlint`, and 11 of 14 local consumers are still below 1.16.0, so they gain actionlint then this hook in one pass — order matters), add `COMPOSITE_SINCE`, extend the table and boundary tests. ~1 h.

Now, at zero risk: one bullet in `docs/RELEASE_CYCLE.md`'s Phase 1 prerequisites — "re-check `inserted_hook_blocks()` rows against the version being cut" — so the rename lesson is a repo artefact, not memory.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 06:09 PM_

The zero-risk half landed: #1723 (merged to `dev` at 6d4a489f) adds the Phase 1 prerequisite to `docs/RELEASE_CYCLE.md` — re-check every `inserted_hook_blocks()` row against the version being cut. The row itself (`'X.Y.Z shellcheck-composite-actions'` after the actionlint row, `COMPOSITE_SINCE`, table + boundary tests in `tests/test_scaffold_preserved_hooks.py`) is release-branch work and keeps this issue open.

---

# [Comment #3]() by [c-vigo]()

_Posted on September 25, 2026 at 08:25 PM_

Done in #1726, merged to `dev` (cc30c0cd): row `1.17.0 shellcheck-composite-actions` after the actionlint row, `COMPOSITE_SINCE` and the boundary tests. The version is fixed now rather than on the release branch because `dev` carries `feat` commits since 1.16.0 with no breaking change, so 1.17.0 is the next train by construction; an upward rename is harmless for the row, and the Phase 1 prerequisite from #1723 covers the downward case. The single-anchor limitation for actionlint-disabled consumers is #1725.

