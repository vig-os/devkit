---
type: issue
state: closed
created: 2026-07-16T17:40:25Z
updated: 2026-07-16T19:44:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1157
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:01.555Z
---

# [Issue 1157]: [promote-release: first-time floating minor/major tag creation fails (422 on POST /git/refs) after publish+merge](https://github.com/vig-os/devkit/issues/1157)

## Summary

`promote-release.yml` → **Move floating tags** fails when a floating **minor** (or major) tag is created for the **first time**. The `POST /git/refs` create-path returns `Reference does not exist (HTTP 422)` even though the step runs as the Release App token. The `promote` and `merge` jobs have already succeeded by then, so the release ships **published + merged** but with the new floating tag **missing** and the workflow marked **failed**.

## Where

`promote-release.yml`, `move_tag()` in the "Move floating major/minor tags" step:

```bash
if [ -n "$current" ]; then
  gh api -X PATCH ".../git/refs/tags/${name}" -f sha="$TARGET_SHA" -F force=true   # existing tag: OK
else
  gh api ".../git/refs" -f ref="refs/tags/${name}" -f sha="$TARGET_SHA"            # NEW tag: 422
fi
```

## Observed (vig-os/commit-action, releasing v0.3.1, run 29519580039)

`DEVKIT_FLOATING_TAGS=major,minor`. `v0` already existed from prior releases; `v0.3` had never been created (first-ever minor float for the repo). Step log:

```
Moved floating tag v0 -> 3a0588ec060d9647bf406e064cf9e6192a431864
gh: Reference does not exist (HTTP 422)
gh: Reference does not exist (HTTP 422)
gh: Reference does not exist (HTTP 422)
##[error]Process completed with exit code 1.
```

- `v0` (existing → PATCH-update path): **succeeded**, moved to the release commit.
- `v0.3` (absent → POST-create path): **failed** 3× (retry-exhausted), then exit 1.

Net effect: GitHub Release `v0.3.1` **published**, PR merged to `main`, `v0` moved — but `v0.3` never created and promote reported failure.

## Likely cause / question

The repo has a **Tag protection ruleset** (`creation`/`update`/`deletion`) whose only bypass actor is the Release App Integration. The **update** path (existing `v0`) bypassed cleanly; the **creation** path (new `v0.3`) surfaced `422 Reference does not exist`. Worth confirming whether the Release App bypass is being applied to the **`creation`** rule for a brand-new floating ref, or whether the create call needs a different shape/endpoint. It reproduces on the first release that introduces a new minor/major floating level.

## Suggested fixes

1. Verify the Release App is an effective bypass actor for the ruleset **`creation`** rule (not just update), OR have devkit's bootstrap pre-create floating tags.
2. Make the step resilient: on create failure, log a clear actionable error naming the exact tag + target SHA and the manual remediation, so promote's failure is diagnosable at a glance.
3. Consider making "Move floating tags" its own idempotent, re-runnable stage decoupled from the post-publish/merge jobs, since publish+merge already succeeded.

## Manual remediation applied (repo is now correct)

Temporarily set the Tag ruleset `enforcement: disabled` (PUT), `POST`-created `refs/tags/v0.3 -> 3a0588e`, restored `enforcement: active` (verified byte-identical to original: bypass/rules/conditions preserved). Final state: `v0`, `v0.3`, and annotated `v0.3.1` all resolve to commit `3a0588e`.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 07:44 PM_

Fixed by #1158 (merged to `dev`). The floating-tag move step now guards the `POST /git/refs` create path and, on a ruleset-denied first-time floating-level create, fails loud with an actionable `::error::` annotation (tag, target commit, ruleset root cause, and the one-off remediation) instead of a cryptic `Reference does not exist`. `docs/MIGRATION.md#first-release-floating-tags` now also covers the steady-state trigger (a live consumer cutting the first release of a new floating level).

Note: the genuine cure — the managed Tag ruleset bypassing the Release App for its `creation` rule — lives in per-consumer onboarding/org-config, not this workflow; tracked separately.

