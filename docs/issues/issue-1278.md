---
type: issue
state: closed
created: 2026-07-27T14:51:19Z
updated: 2026-07-28T13:42:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1278
comments: 1
labels: bug, priority:low, area:workflow, effort:small, semver:patch
assignees: none
milestone: 1.4.3
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:56.912Z
---

# [Issue 1278]: [sync-issues template: always()-cleanup steps assume the retry shim that may not exist on early job failure](https://github.com/vig-os/devkit/issues/1278)

## Description

The scaffolded `sync-issues.yml` cache-management step (`assets/workspace/.github/workflows/sync-issues.yml`, "Attempting to delete old cache…") calls the `retry` wrapper, which is provided as a `BASH_ENV` shim by the `setup-devkit-toolchain` composite. On healthy runs this works (e.g. vig-os/commit-action run 2026-07-27: `Cache deleted successfully`).

But the cleanup step runs `if: always()`: when the job fails **before** toolchain setup — live example: exo-pet/vault runs failing at "Generate a token" (missing App secrets), run 2026-07-26T05:30Z — the shim was never installed and the step degrades:

```
/home/runner/work/_temp/….sh: line 7: retry: command not found
No cache found with key: sync-issues-state-exo-pet/vault (this is OK for first run)
```

Two defects on that path:
1. `retry: command not found` — no retries; and because the call sits in `CACHE_ID=$(retry … | head -1)`, the pipeline exits 0 via `head`, so `set -e` never fires.
2. The empty `CACHE_ID` silently takes the "No cache found" branch even when a cache exists — the anti-collision deletion the step exists for is skipped without signal.

## Proposed fix

Make the cleanup step self-sufficient, e.g. guard with a fallback shim at the top of the step:

```bash
command -v retry >/dev/null || retry() { shift $(( $(echo "$@" | grep -c '^--') )); "$@"; }
```

…or simpler: define the one-shot fallback `retry() { while [ "$1" != "--" ]; do shift; done; shift; "$@"; }`, or condition the step on toolchain-setup success instead of `always()` (the cache save is equally pointless when sync never ran).

Cosmetic/robustness only — healthy runs are unaffected.

Surfaced during the 2026-07-27 sync-issues failure diagnosis (exo-pet consumer credential gap).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 28, 2026 at 01:42 PM_

Fixed by PR #1286 (merged to dev, milestone 1.4.3). Both the scaffold template and devkit's own sync-issues.yml now carry a one-shot retry fallback in the always()-cleanup step.

