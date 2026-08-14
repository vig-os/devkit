---
type: issue
state: closed
created: 2026-08-14T07:19:11Z
updated: 2026-08-14T11:43:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1504
comments: 1
labels: feature
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:15.444Z
---

# [Issue 1504]: [[FEATURE] Release train: collect the single human approval at promote, not before finalize](https://github.com/vig-os/devkit/issues/1504)

### Description

One release cycle currently costs two human approvals of the **same PR**. The `release.yml` `validate` job hard-fails a final unless the release PR is `APPROVED` (`release.yml:316-368`); the `finalize` job then pushes its own commits (CHANGELOG date stamp, regenerated docs, sync-issues) to `release/X.Y.Z`, which dismisses that approval via `dismisses_stale_reviews: true` on Main protection (vig-os/org-config#118); `promote-release.yml` then demands a fresh approval (`promote-release.yml:293-360` and `:544-583`, #1487). The cost is documented as known and deliberate in #1474, `docs/RELEASE_CYCLE.md:398-426` and `:531-539`, and downstream recipe headers.

#1474 decided to keep both gates, with the explicit condition: *"Revisit only if the two-person case is explicitly ruled out for consumers."* It now is — the org is single-maintainer, and the second approval differs from the first only by devkit's own bot commits.

**Proposed change:**

1. In `release.yml` `validate`, drop the `reviewDecision` assertion for `release-kind=final` (candidates already skip it, #902). The **promote-side gates stay exactly as they are** — both the hoisted `validate` check and the `merge` re-check (#1487) — and become the single human approval of the cycle.
2. Add a `just abandon-release X.Y.Z` recipe as the first-class rejection path at promote time: delete the **draft** GitHub Release and the `X.Y.Z` tag via the Release App (Tag-protection bypass — same machinery as the RC prune, `promote-release.yml:648-651`), close the release PR, delete `release/X.Y.Z`. Safe only while the release is a draft; a published release tombstones the tag name (`RELEASE_CYCLE.md`, the 1.5.0 ghost).

This is a strict improvement in evidence quality, not a relaxation: the one approval now lands on the release content **exactly as it ships**, finalize commits included — today's first approval covers content that subsequently changes.

### Files / Modules in Scope

- `.github/workflows/release.yml` (validate-job approval gate, final kind only)
- `justfile.gh` (`abandon-release` recipe; comment updates on `finalize-release` / `promote-release`)
- `docs/RELEASE_CYCLE.md`, `docs/DOWNSTREAM_RELEASE.md` (remove the approve-before-finalize and re-approve steps; document the new single gate and the abandon path)
- Rendered consumer workflow variants (trunk + gitflow)

### Out of Scope

- `promote-release.yml` approval checks — unchanged, per the #1487 rationale (validate-side check prevents publishing an irreversible release that can't merge)
- Any ruleset change: `dismisses_stale_reviews` stays `true`, review count stays 1
- The smoke-test cross-repo gate — tracked separately in #1506

### Invariants / Constraints

- Promote still refuses without a live approval, both in workflow checks and at the platform: the Release App is not a Main-protection bypass actor, so `gh pr merge` fails without an approval regardless of workflow logic.
- `actions_can_approve_pull_request_reviews: false` stays org-wide; no workflow identity may approve.
- Candidates remain approval-free (#902).

### Acceptance Criteria

- [ ] A full release train (prepare → candidates → finalize → smoke → promote) requires exactly **one** human approval, collected after finalize and before promote
- [ ] `finalize-release` no longer asserts `reviewDecision` for finals; promote-side checks unchanged
- [ ] `just abandon-release` exists, is documented, and its draft-only precondition is enforced in the recipe
- [ ] `RELEASE_CYCLE.md` / `DOWNSTREAM_RELEASE.md` no longer instruct a re-approval

### Changelog Category

Changed

### Additional Context

Revisits the #1474 decision under its own stated revisit condition. Related: #1487 (promote-side hoist), #902 (candidate skip), vig-os/org-config#118 (stale-review dismissal), #1506 (smoke gate), vig-os/org-config#167 (companion ruleset change).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 11:43 AM_

Delivered by #1510 (merged to dev 2026-08-14): release.yml validate no longer requires an approved release PR for finals, the promote-side gates are the cycle's single human approval, and `just abandon-release` + `abandon-release.yml` ship as the first-class rejection path. Docs updated in 8259be9a. Consumer variant of the abandon workflow split out to #1511.

