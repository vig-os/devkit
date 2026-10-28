---
type: issue
state: open
created: 2026-10-27T08:54:43Z
updated: 2026-10-27T12:04:14Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1932
comments: 3
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:01.016Z
---

# [Issue 1932]: [#1908 S6: Site leak-check hook point](https://github.com/vig-os/devkit/issues/1932)

Implementation sub-issue **S6** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:* §10 leak check.
- *Files:* `packages/vig-utils/src/vig_utils/site_leak_check.py`,
  `packages/vig-utils/pyproject.toml` (the `site-leak-check` console-script
  line), `nix/hooks.nix` (a separate entry from S5), and tests.
- *Acceptance:*
  - no pattern file: exit 0 and silent;
  - the `DEVKIT_LEAK_PATTERNS` and `.site/` lookup order;
  - a staged match fails, with redacted output;
  - a tracked or in-tree pattern file is an error;
  - `--all-files` mode scans the tree.

Refs #1908
---

# [Comment #1]() by [gerchowl]()

_Posted on October 27, 2026 at 10:54 AM_

S4 coordination for #1930 / PR #1938: `.site/leak-patterns.toml` keeps its ADR §10 name and location. S4 will validate TOML parsing and the optional `[[rules]]` array shape (each rule has string `id` and `regex`) only. It will not apply site-binding credential-key or URI-userinfo restrictions to gitleaks configs; `secretGroup`, userinfo-matching regexes, and allowlists remain supported. Gitleaks retains semantic validation. The module docstring will record this boundary.


---

# [Comment #2]() by [gerchowl]()

_Posted on October 27, 2026 at 11:33 AM_

Implemented point-of-use validation: a present leak-patterns.toml must contain at least one [[rules]] entry with nonempty string id and regex, otherwise site-leak-check exits 2 and names the file without printing patterns; a missing file remains a silent no-op.


---

# [Comment #3]() by [gerchowl]()

_Posted on October 27, 2026 at 12:01 PM_

Final point-of-use rule: a pattern file must be self-contained (any [extend] table, including empty tables and case variants, exits 2 naming the file) and contain at least one [[rules]] entry with a nonempty string id plus a nonempty regex or path; path-only gitleaks rules are usable, and a missing file remains a silent no-op.

