---
type: issue
state: closed
created: 2026-08-07T15:04:29Z
updated: 2026-08-07T16:29:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1377
comments: 1
labels: bug, area:ci
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:58.647Z
---

# [Issue 1377]: [promote-release: floating-tag creation via POST /git/refs is not covered by the Release App's ruleset bypass — switch move_tag() to git push](https://github.com/vig-os/devkit/issues/1377)

## Context

The `floating-tags` job in the downstream `promote-release.yml` template (`assets/workspace/.github/workflows/promote-release.yml`) creates-or-updates floating tags via the REST API: `PATCH /git/refs/tags/<name>` when the ref exists, `POST /git/refs` when it does not. The create path fails on the **first release of every new floating level** with the opaque `HTTP 422 "Reference does not exist"` — hit on `vig-os/commit-action` v0.3.1 (#1157) and again today on `vig-os/sync-issues-action` v0.5.0 ([run 31186320919](https://github.com/vig-os/sync-issues-action/actions/runs/31186320919): `v0` moved fine, `v0.5` create failed 3×).

#1157 was closed by #1158 with diagnostics + the MIGRATION.md runbook only; the closing comment deferred the "genuine cure" to a separate issue that was never filed. This is that issue.

## Root cause — GitHub bug, not configuration

#1157 hypothesized the Release App might not be a bypass actor for the `creation` rule. That is now **disproven**: the live Tag ruleset (org-config `otterdog/vig-os/vig-os.jsonnet`, verified on sync-issues-action ruleset 19011483) grants `vig-os-release-app` (app 2930017, Integration) `bypass_mode: always` on the whole ruleset (`creation`, `update`, `deletion`).

The repo's rule-suite audit log for today's 0.5.0 release shows the same installation token, same day:

| Operation | Path | Rule-suite result |
|---|---|---|
| Create `v0.5.0-rc1`, `v0.5.0` | `git tag` + `git push` (release-publish.yml) | creation rule `fail` → overall **`bypass`** ✓ |
| Move `v0` | REST `PATCH /git/refs/tags/v0` | **`bypass`** ✓ |
| Delete `v0.5.0-rc1` | REST `DELETE` | **`bypass`** ✓ |
| Create `v0.5` | REST **`POST /git/refs`** | **422, and no rule-suite entry at all** ✗ |

So `POST /git/refs` is the only path where Integration bypass is not honored for `creation`; it returns a wrong-sounding 422 and does not even log a rule evaluation. All other 422 causes (malformed ref, bad SHA, wrong token) are eliminated — the same token PATCHed another tag ref seconds earlier with the same SHA, and a human push without bypass gets the *correct* `GH013 Cannot create ref due to creations being restricted`. No public GitHub report covers this asymmetry (closest is github/rest-api-description#4887 on 422 vagueness); worth reporting upstream separately.

## Proposed fix

Rewrite `move_tag()` to mutate tags via **git push with the App installation token**, which is empirically proven to honor the bypass for creation (it is exactly how release-publish.yml creates the release tags today), and unifies create + move into one branch-free path:

```bash
git push "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" \
  --force "${TARGET_SHA}:refs/tags/${name}"
```

Details to preserve:

1. **Idempotence check stays** — the `gh api GET` read + skip-when-already-at-target is unaffected by the bug.
2. **Token must be plumbed explicitly** (URL form above, or checkout-style `http.extraheader` basic auth). Do **not** rely on the checkout step's persisted credentials — those are the default `github.token`, which has no bypass (the classic failure mode in community reports of "bypass doesn't work").
3. **Keep the `::error` annotation + MIGRATION.md fallback** from #1158 for pushes that fail for other reasons; update its wording (the "grant a creation bypass" remediation is moot — the bypass already exists and the REST path ignores it).
4. Leave a comment in the script explaining *why* push is used instead of `POST /git/refs`, so the REST trap isn't reintroduced.
5. `tests/test_floating_tags.py` pins the annotation shape — adjust alongside.

This matches ecosystem practice: `actions/checkout`'s `update-main-version.yml` and GitHub's own action-versioning guidance move floating tags via force-push, never via `createRef`.

## Out of scope / follow-ups

- Reporting the `POST /git/refs` bypass asymmetry to GitHub (community discussion or support ticket).
- Optional org-config hardening: switch the App's bypass to the newer `exempt` mode (2025-09 changelog: "rules will not be run for that actor") — redundant once push is used.
- MIGRATION.md "first-release floating tags" runbook can shrink to a note for consumers on pre-fix devkit versions.

## Acceptance criteria

- [ ] First-ever creation of a floating level (`vX` or `vX.Y`) succeeds in the promote run with the Tag ruleset active and Release-App-exclusive.
- [ ] Subsequent moves still succeed and remain idempotent (re-run safe).
- [ ] A push failure still fails the job loudly with the actionable annotation.
- [ ] Verified on a consumer repo's next `X.Y.0` release (first new minor of a train).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 04:29 PM_

Fixed on dev by PR #1379: move_tag() in the scaffold promote-release.yml now mutates floating tags via git push with the explicitly-plumbed App installation token (the path proven to honor the Integration ruleset bypass), replacing the POST /git/refs create path that returned the opaque 422. Idempotence guard kept; ::error annotation and the MIGRATION.md runbook updated. Live proof lands with the first new floating level on a consumer's next release.

