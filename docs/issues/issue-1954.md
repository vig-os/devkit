---
type: issue
state: open
created: 2026-10-29T01:27:35Z
updated: 2026-10-29T01:27:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1954
comments: 0
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:29.965Z
---

# [Issue 1954]: [site-init: follow-up hardening and docs from S4 final review](https://github.com/vig-os/devkit/issues/1954)

Follow-ups from the final re-review of PR #1938 (S4 #1930). None of them blocks; each was confirmed by a probe.

1. **Undocumented initialiser-discovery limits.**
   - A hardlink created *outside* the repo that points at a repo file still runs, because its resolved path is outside the repo. A clone can't create one.
   - `GIT_DIR`/`GIT_WORK_TREE` pointing elsewhere moves the root.
   - A committed `bin/git` found through an in-tree PATH entry is run by `repository_root()`, and it can choose the root.

   None of these adds exposure beyond the user's own PATH and environment. Still, the module docstring ("never search relative or in-tree PATHs") covers discovery only.
   Fix: either look up `git` through the same PATH filter as discovery, or document the three limits in ADR §9 known limits and in the docstring.
2. **Cf format characters in locations.** These are accepted: U+200B, U+FEFF, the bidi overrides U+202E/U+2066 and others. Port 99999 is also accepted, and `az://acct@x` gets through `validate_location` (`check_credentials` in `validate()` catches that one).
   Fix: reject Unicode category Cf, and range-check ports. Add tests.
3. **An unrelated PATH executable aborts site-init.** An executable named `devkit-site-init-Leak-Patterns` anywhere on PATH aborts `site-init a` with exit 2. A reserved-name candidate should be skipped with a warning, not abort an unrelated selection. Alternatively, document the abort as intended.
4. **CHANGELOG wording.** The entry says pattern validation is shared "with the leak checker", which isn't true until S6 (#1932) lands. Reword it, or check it after S6 merges.

Refs: #1930

