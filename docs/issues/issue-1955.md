---
type: issue
state: open
created: 2026-10-29T01:35:25Z
updated: 2026-10-29T02:34:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1955
comments: 1
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:29.251Z
---

# [Issue 1955]: [devkit-upgrade hook migration: message and fold-gate follow-ups from S3 review](https://github.com/vig-os/devkit/issues/1955)

Follow-ups from the final re-review of PR #1949 (S3 #1929). Each was confirmed by a probe. They are consumer-facing message quality in the adoption PRs, so fix them before 1.19.0 ships.

1. **Pending lines that never go away on hosted-only repos.** A repo with neither `CI_RUNNER_SMALL` nor the legacy `DEVKIT_CI_RESOLVE_RUNNER` (e.g. a public repo on hosted runners) gets 4 "pending: set CI_RUNNER_SMALL" lines in every upgrade. Folding there changes nothing, because the SMALL expression falls back to the same hosted runner. The gate exists only to protect the legacy-variable case. Fold when neither variable is set, and keep the pending line only when the legacy variable is set and SMALL isn't valid. Update MIGRATION.md accordingly.
2. **Quoted stock values count as drift.** `runs-on: 'ubuntu-26.04'` (and the double-quoted form) is reported as drift instead of being folded. Normalise YAML scalar quoting before comparing against `CI_RUNNER_HOOK_STOCK`.
3. **Jobs with only `uses:`.** A job with no `runs-on` (a reusable-workflow call) is reported as drift ("no job runs-on could be classified"), which blocks the delete-legacy-variable hint forever. Such jobs need no migration: skip them, or report them as not applicable.
4. **Wording.**
   - With a valid SMALL already set, the message still says "Set CI_RUNNER_SMALL; keep DEVKIT_CI_RESOLVE_RUNNER…".
   - The drift message tells a consumer who deliberately pinned a custom runner to move it to the SMALL expression. It should say that a custom value is left as-is and only needs review.
5. **Out-of-scope heading change.** The PR reworded the existing pre-commit drift/reconcile headings in the PR-body builder. The weaker "review by hand" now also covers retired blocks that do need folding by hand. Restore the precise instruction for those blocks.

Each item needs a test that fails before the fix.

Refs: #1929

---

# [Comment #1]() by [gerchowl]()

_Posted on October 29, 2026 at 02:34 AM_

Two wording nits from the final re-review of PR #1956 (S7 #1933) belong here too, since they're consumer-facing migration text:
- `docs/MIGRATION.md` ~424: "the variable wins whenever both are set" comes right after `DEVKIT_CI_RESOLVE_RUNNER`, so it reads as that variable beating the key. Say "a `CI_RUNNER_*` variable wins over the `.vig-os` key".
- `docs/MIGRATION.md` ~444-447: the N+2 `DEVKIT_CI_RUNNER` tombstone omits the ADR's foreign-run case, which only warns. Add it.

