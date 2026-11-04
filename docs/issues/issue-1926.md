---
type: issue
state: open
created: 2026-10-27T08:54:31Z
updated: 2026-10-27T08:54:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1926
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:03.948Z
---

# [Issue 1926]: [#1908 S1d: Runner diagnostics](https://github.com/vig-os/devkit/issues/1926)

Implementation sub-issue **S1d** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* every §3 diagnostic except the malformed-variable error (including
  the opted-in-class `::warning::`):
  - the full-text legacy-key `::warning::` (the primary migration channel,
    §6);
  - the legacy-variable warning;
  - the whitespace-only warning;
  - the partial-setup `::notice::`;
  - the private no-variables `::notice::` and its step-summary line;
  - the `runner-sources` step-summary table.
- *Files:* `resolve-toolchain/action.yml` (the diagnostics section) and the
  diagnostic tests in `tests/test_ci_runner.py`.
- *Acceptance:*
  - the legacy-key warning names every unset required class, the
    repository-level hint, the delete-the-key step and the `MIGRATION.md`
    anchor, and never the label;
  - the partial-setup notice: the default map with only SMALL set → no
    notice; `DEVKIT_CI_LANE_SIZES=test=large` with SMALL and LARGE set → no
    notice, and with only SMALL set → a notice and a `::warning::` naming
    `CI_RUNNER_LARGE` and the `test` lane, with that lane still on the hosted
    default; a set but unused LARGE is never reported;
  - the opt-in warning also fires with no variable at all and an override in
    `.vig-os` (the after-strip case), never on a foreign run, and not for a
    class sourced from `legacy-key`;
  - the private no-variables notice fires as an annotation, is silenced by
    variables set to `ubuntu-26.04`, and does not fire on a public repo or a
    foreign run;
  - the whitespace-only warning names the offending variable (tested with
    `CI_RUNNER_LARGE` under a lane override).

Refs #1908
