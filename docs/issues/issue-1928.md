---
type: issue
state: open
created: 2026-10-27T08:54:35Z
updated: 2026-10-27T08:54:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1928
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:02.955Z
---

# [Issue 1928]: [#1908 S2: Remaining scaffolded workflows](https://github.com/vig-os/devkit/issues/1928)

Implementation sub-issue **S2** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* `sync-issues`, `sync-main-to-dev`, `prepare-release`,
  `prepare-hotfix`, `release`, `release-core`, `release-publish`,
  `promote-release`, `abandon-release` and their resolvers per §4; the
  `runner-json` → `runners` input on the managed reusables; the
  `ci-extension.yml` header comment for new scaffolds (`runner-json` is now the
  `extension` lane, not `DEVKIT_CI_RUNNER`-derived); new-scaffold seeded
  hooks on the SMALL direct expression; `devkit-upgrade.yml` per (e).
- *Files:* those workflow files under `assets/workspace/.github/workflows/`,
  and the release-train and hook tests in `tests/test_ci_runner.py`. Not
  disjoint from S1: different test functions in the same file.
- *Acceptance:*
  - each resolver passes all four inputs;
  - each job's class matches §4;
  - managed reusables declare `runners`;
  - the seeded-hook input contract is unchanged;
  - seeded hooks use the new expression;
  - S1's shape test and resolver-expression test are widened to every
    scaffolded workflow, including `assets/smoke-test/.github/workflows/ci-extension.yml`.

Refs #1908
