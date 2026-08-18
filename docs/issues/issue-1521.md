---
type: issue
state: closed
created: 2026-08-14T17:08:38Z
updated: 2026-08-17T10:19:11Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1521
comments: 1
labels: feature, area:ci, effort:small
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:16.994Z
---

# [Issue 1521]: [[FEATURE] Fingerprint check: give the emails blocklist the #274 context guard (or strip code spans)](https://github.com/vig-os/devkit/issues/1521)

Follow-up to #1516 (the 1.10.0 train blocker). The **emails** list in `.github/agent-blocklist.toml` is matched as a bare, case-insensitive substring over the whole content (`contains_agent_fingerprint` in `packages/vig-utils/src/vig_utils/utils.py`), while **names** only match on lines with an attribution-context phrase (#274). Any changelog entry or PR body that *describes* a bot-identity bug therefore blocks its own release PR.

Options (either suffices; see #1516 for the incident):
- Apply the `_ATTRIBUTION_CONTEXT_RE` line guard to email matching too, or
- Add an `allow_patterns` entry / pre-pass that strips inline code spans before matching.

Acceptance: the 1.10.0-era #1503 changelog wording (with the literal restored) passes `check-pr-agent-fingerprints`, while a real `Co-authored-by`/bot-identity attribution still fails.

Refs: #1516
---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 10:19 AM_

Fixed in #1536 (merged to dev): contains_agent_fingerprint now strips single-line inline code spans before matching the emails blocklist. Chose the code-span option over the _ATTRIBUTION_CONTEXT_RE guard, which fails acceptance 2: the context regex matches neither Signed-off-by: nor Author: lines, so it would have let real attributions through. Acceptance verified with the verbatim pre-#1516 changelog wording (passes) and Co-authored-by/Signed-off-by/Author attributions (still fail). Names guard (#274) and trailer rules untouched.

