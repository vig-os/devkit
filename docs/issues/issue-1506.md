---
type: issue
state: closed
created: 2026-08-14T07:33:09Z
updated: 2026-08-14T11:43:06Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1506
comments: 2
labels: feature
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:14.998Z
---

# [Issue 1506]: [[FEATURE] Smoke-test gate: drop the human approval of the smoke release PR](https://github.com/vig-os/devkit/issues/1506)

### Description

The cross-repo final gate makes a human approve the `devkit-smoke-test` release PR while the dispatch listener polls `reviewDecision` for up to 30 minutes (rendered `repository-dispatch.yml:727`; `docs/CROSS_REPO_RELEASE_GATE.md:61-68`). This gate is a **workaround, not a control**: it exists only because #1391 found that GitHub computes `reviewDecision` solely when the base branch requires reviews, and the org blocks Actions-token approvals. The PR it guards is entirely bot-authored scaffold output; the approval carries no information — the real controls are green smoke CI and the published smoke release that devkit's promote gate already validates.

**Proposed change:** remove the approval requirement outright.

- In `assets/smoke-test/`, remove the `Gate final release on human approval of release PR` poll from `repository-dispatch.yml`, and audit which `reviewDecision` assertions in the smoke repo's rendered release workflows (`release-core.yml` validate, `promote-release.yml`) the dispatch flow exercises — remove those too. They must be **compiled out, not left to fall through**: with a review count of 0, `reviewDecision` comes back empty and the #438 fallback counts zero approved reviews and fails.
- The companion org-config change request vig-os/org-config#167 drops `required_approving_review_count` from 1 to 0 on `devkit-smoke-test`'s Main protection.

**Rejected alternative — auto-approval by a second App identity (#1391 option 1):** it manufactures review evidence that is always granted and therefore meaningless (actively bad for the QMS record), adds Commit App secrets and a standing rubber-stamp workflow to the smoke repo (a small but real attack surface), and rests on the never-exercised assumption that App installation tokens are exempt from the org's approval block.

### Files / Modules in Scope

- `assets/smoke-test/.github/workflows/repository-dispatch.yml`
- Whichever smoke-rendered release workflows the dispatch flow exercises (audit as part of this issue)
- `docs/CROSS_REPO_RELEASE_GATE.md`, `docs/RELEASE_CYCLE.md` (smoke-approval steps removed)

### Out of Scope

- The org-config ruleset change itself (vig-os/org-config#167)
- Devkit's own release-PR approval flow (#1504)
- Any weakening of the smoke validation: CI-green and published-release requirements unchanged

### Invariants / Constraints

- **Sequencing:** the live listener runs from the smoke repo's `main` at dispatch time, so the propagated workflow change (via an explicit upgrade PR to `devkit-smoke-test`, not just the template merge) **and** the org-config ruleset change must both land before the next release train. Order between the two doesn't matter — either one alone breaks the next train (old poll + count 0 → empty decision → fail; new workflows + count 1 → unapprovable merge).
- Devkit's promote gate still requires a **published** smoke release for the tag — unchanged.

### Acceptance Criteria

- [ ] No human interaction is required in `devkit-smoke-test` during a devkit final release
- [ ] All `reviewDecision` assertions exercised by the dispatch flow are removed from the smoke template (none left to hit the #438 fallback)
- [ ] Upgrade PR to `devkit-smoke-test` merged before the next train; sequencing note recorded in `CROSS_REPO_RELEASE_GATE.md`

### Changelog Category

Changed

### Additional Context

Follow-up to #1391 (the interim manual gate), resolving it by removal rather than by its "option 1". Related: #438 (fallback), #1504 (single approval at promote), vig-os/org-config#167 (companion ruleset change).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 08:48 AM_

**Design decision (amends the "compiled out" acceptance criterion).**

The smoke repo's rendered release workflows ARE the shared consumer scaffold (`assets/workspace/`), and the scaffold-drift gate is active in the smoke repo (`DEVKIT_DRIFT_CHECK` unset ⇒ true) — the gate re-scaffolds in normal mode from `.vig-os`, so a smoke-only render divergence in `promote-release.yml` would need a new persisted manifest key plus anchored sed surgery on a 30 KB workflow.

Instead, the promote-side approval checks in the scaffold `promote-release.yml` (validate + merge) become **protection-aware**: they query the base branch's rules (`gh api repos/{repo}/rules/branches/<base>`) and, when `required_approving_review_count` resolves to 0, log an explicit skip of the approval assertion (draft, CI, and mergeability checks unchanged). This is drift-safe, needs no installer changes, and fixes promote for the whole count-0 class (solo-adoption repos), smoke included.

Amended AC: the *listener* gate (`Gate final release on human approval of release PR`) is still removed outright from `repository-dispatch.yml`; the promote-side `reviewDecision` assertions remain in the shared template but are skipped by an explicit protection-count guard — never left to hit the #438 fallback. Known limitation (documented in-workflow): the rules endpoint sees rulesets, not classic branch protection; classic-protection repos degrade to the platform's own merge-time refusal (fail-late, not fail-open).

Companion ruleset change vig-os/org-config#167 is already applied, so the next final train is blocked until the listener change reaches smoke `main` via a direct hotfix PR (precedent devkit-smoke-test#345/#353).

---

# [Comment #2]() by [c-vigo]()

_Posted on August 14, 2026 at 11:43 AM_

Delivered: devkit side by #1510 (approval poll removed, promote gates made protection-aware), smoke-repo listener by vig-os/devkit-smoke-test#375 (merged 2026-08-14), and Main protection review count dropped to 0 via vig-os/org-config#167. The smoke leg now runs unattended end-to-end.

