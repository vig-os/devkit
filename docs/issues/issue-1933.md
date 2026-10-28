---
type: issue
state: open
created: 2026-10-27T08:54:44Z
updated: 2026-10-27T08:54:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1933
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:00.482Z
---

# [Issue 1933]: [#1908 S7: `MIGRATION.md` self-hosted rewrite](https://github.com/vig-os/devkit/issues/1933)

Implementation sub-issue **S7** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:*
  - rewrite `docs/MIGRATION.md` "Run CI on self-hosted runners" around the
    variables: repository level on GitHub Free, fork safety and decision (f)'s
    remedy, size classes and the lane override, and the deprecation timeline
    including the migrating-adoption and consumer-state tombstone (§6);
  - a "CI never starts on a private repo" entry (§3 notice limit);
  - the whitespace-only `CI_RUNNER_SMALL` symptom (§1);
  - replace the site-specific example label and the `gh variable set` value
    with `<label>`;
  - update the manifest key table.
- *Files:* `docs/MIGRATION.md` only.
- *Acceptance:*
  - docs lint passes;
  - every §3 diagnostic's `MIGRATION.md` anchor resolves;
  - the section contains no site label.

Refs #1908
