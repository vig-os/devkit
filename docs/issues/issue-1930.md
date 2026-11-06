---
type: issue
state: open
created: 2026-10-27T08:54:39Z
updated: 2026-10-27T08:54:39Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1930
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:02.038Z
---

# [Issue 1930]: [#1908 S4: `.site/` convention and site-init hook](https://github.com/vig-os/devkit/issues/1930)

Implementation sub-issue **S4** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* §8–§9: vig-utils `site_config.py` (`check-site-config` with
  `--print-path`, `site-init`); the managed-justfile recipe `site-init`; the
  template `.gitignore` gains `.site/` and `.aws/`.
- *Files:* `packages/vig-utils/src/vig_utils/site_config.py`,
  `packages/vig-utils/pyproject.toml`, `assets/workspace/justfile`,
  `assets/workspace/.gitignore`, and new tests.
- *Acceptance:*
  - schema validation, including credential-key and userinfo rejection;
  - active-site lookup, including the ambiguity error;
  - discovery with zero, one and several fixture initialisers;
  - a failing or invalid initialiser leaves no files;
  - `--force` semantics;
  - the non-TTY template;
  - `.site/` and `.aws/` are ignored in a rendered scaffold.

Refs #1908
