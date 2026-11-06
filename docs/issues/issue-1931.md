---
type: issue
state: open
created: 2026-10-27T08:54:41Z
updated: 2026-10-27T08:54:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1931
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:01.495Z
---

# [Issue 1931]: [#1908 S5: Env-only lint](https://github.com/vig-os/devkit/issues/1931)

Implementation sub-issue **S5** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* §10 lint.
- *Files:* `packages/vig-utils/src/vig_utils/check_hardcoded_endpoints.py`,
  `packages/vig-utils/pyproject.toml` (the `check-hardcoded-endpoints`
  console-script line), `nix/hooks.nix`
  (hook entry), `.pre-commit-config.yaml` (devkit's own), and tests.
- *Acceptance:*
  - each rule fires on a positive fixture;
  - references, RFC 2606 hosts and the pragma pass;
  - devkit's own tree passes;
  - the hook is present and enabled on the consumer surface.

Refs #1908
