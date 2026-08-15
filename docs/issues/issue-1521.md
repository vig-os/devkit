---
type: issue
state: open
created: 2026-08-14T17:08:38Z
updated: 2026-08-14T17:08:38Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1521
comments: 0
labels: feature, area:ci, effort:small
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-08-15T02:57:59.030Z
---

# [Issue 1521]: [[FEATURE] Fingerprint check: give the emails blocklist the #274 context guard (or strip code spans)](https://github.com/vig-os/devkit/issues/1521)

Follow-up to #1516 (the 1.10.0 train blocker). The **emails** list in `.github/agent-blocklist.toml` is matched as a bare, case-insensitive substring over the whole content (`contains_agent_fingerprint` in `packages/vig-utils/src/vig_utils/utils.py`), while **names** only match on lines with an attribution-context phrase (#274). Any changelog entry or PR body that *describes* a bot-identity bug therefore blocks its own release PR.

Options (either suffices; see #1516 for the incident):
- Apply the `_ATTRIBUTION_CONTEXT_RE` line guard to email matching too, or
- Add an `allow_patterns` entry / pre-pass that strips inline code spans before matching.

Acceptance: the 1.10.0-era #1503 changelog wording (with the literal restored) passes `check-pr-agent-fingerprints`, while a real `Co-authored-by`/bot-identity attribution still fails.

Refs: #1516
