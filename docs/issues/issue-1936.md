---
type: issue
state: open
created: 2026-10-27T08:54:50Z
updated: 2026-10-27T08:54:50Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1936
comments: 0
labels: feature
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:58.746Z
---

# [Issue 1936]: [#1908 S9: Removal (release N+2)](https://github.com/vig-os/devkit/issues/1936)

Implementation sub-issue **S9** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* §6 N+2: delete the legacy arms, keep the tombstones, remove the
  `runner-json` alias, and drop the template key. The direct expression of the
  `resolve-toolchain` jobs and resolvers is unchanged (§3: the legacy-variable term carries the tombstone).
- *Files:* `resolve-toolchain`, the scaffolded workflows, `.vig-os`,
  `init-workspace.sh`, tests, `MIGRATION.md`, and CHANGELOG `### Removed`.
- *Acceptance:*
  - consumer-state tombstone: a non-inert key → `::error::` with the full
    text; an inert key (every required variable set) → `::warning::` and
    green; a foreign run → `::warning::`;
  - the variable tombstone error and warning;
  - the companion of S3's "adopt N+1 before releasing N to main" test;
  - `DEVKIT_CI_RESOLVE_RUNNER` appears in `runs-on` only as the term before
    the hosted default in the `resolve-toolchain` jobs and resolvers, never
    in a seeded hook.
- Blocked by release N+1 shipping.

Refs #1908
