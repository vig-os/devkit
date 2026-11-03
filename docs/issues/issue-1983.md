---
type: issue
state: open
created: 2026-11-02T04:00:09Z
updated: 2026-11-02T04:00:09Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1983
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-02T04:55:23.931Z
---

# [Issue 1983]: [vulnix-gate: lint scoped register entries (CVE@pname@version) and fail on malformed forms](https://github.com/vig-os/devkit/issues/1983)

Follow-up from the #1977 review (PR #1979).

The vulnix gate now accepts scoped exceptions of the form `CVE-ID@pname@version`. A malformed scoped entry, for example `CVE@brotli`, `CVE@@` or an extra `@`, fails closed: it suppresses nothing, so the gate goes red. But nothing lints the format, so a typo only shows up as a confusing red gate at release time.

Acceptance:
- `check-expirations` (or a register lint run in PR CI) rejects malformed scoped entries with a clear message.
- Edge cases `CVE@None@None` and empty pname/version are rejected explicitly.
- The full-image vulnix scan of PR closures is tracked separately: today PR CI checks only expirations, and vulnix runs nightly and at release time.

Refs: #1977
