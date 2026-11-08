---
type: issue
state: open
created: 2026-10-29T01:09:03Z
updated: 2026-10-29T01:09:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1953
comments: 0
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:30.573Z
---

# [Issue 1953]: [devkit-upgrade: read_manifest_value silently drops a key after an earlier blank duplicate](https://github.com/vig-os/devkit/issues/1953)

Found by the pre-mortem of PR #1949 (S3 #1929). It predates that PR.

**Defect.** `read_manifest_value` (devkit-upgrade / install path that reads `.vig-os`) stops at the first matching key line even when that line has an empty value. If a blank template line such as `DEVKIT_CI_RUNNER=` appears before the consumer's own `DEVKIT_CI_RUNNER=<label>` line, the consumer's value is silently lost. No message is printed.

**Expected.** A duplicate key in `.vig-os` is reported, either as an error or as a warning naming the key and both line numbers. Otherwise the reader takes the documented one (last wins, or first non-empty), and that rule is tested. Never a silent drop.

**Acceptance.**
- A test with a blank-then-set duplicate fails before the fix and passes after it.
- The chosen rule is documented where `.vig-os` keys are documented.

