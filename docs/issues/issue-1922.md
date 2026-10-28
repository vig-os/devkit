---
type: issue
state: open
created: 2026-10-27T08:19:28Z
updated: 2026-10-27T08:19:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1922
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:04.977Z
---

# [Issue 1922]: [Managed docs render: vacuous drift-test assertion, redundant Refs cross-reference in all-exempt mode](https://github.com/vig-os/devkit/issues/1922)

Follow-ups from the review of #1911, which fixed #1910 (manifest-aware SECURITY.md and COMMIT_MESSAGE_STANDARD.md):

1. **A test assertion can never fail.** `tests/test_scaffold_drift.py` (~L346) asserts `"The Refs line is optional" not in standard`, but the rendered text is ``The `Refs:` line is optional`` (with backticks), so the assertion is always true. Assert on the exact rendered phrase, and show that it fails when the render is reverted.
2. **Redundant cross-reference in `all` mode.** When every type is exempt, the Refs bullet in the rendered `docs/COMMIT_MESSAGE_STANDARD.md` still ends with "See [Exemptions](#exemptions) for types where `Refs:` is optional" after already saying "Optional for all approved types". The rendering in `assets/init-workspace.sh` (~L3345) should drop the cross-reference in that mode.
3. **Undocumented drop.** In non-default renders, the "Consumer repos may name a different exempt set…" paragraph is removed. This is fine for a rendered document, but the managed-docs ADR (`docs/rfcs/ADR-manifest-aware-managed-docs.md`) should say so.

Refs #1910

