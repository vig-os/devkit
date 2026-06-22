---
type: issue
state: open
created: 2026-06-19T12:53:02Z
updated: 2026-06-21T19:45:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/604
comments: 1
labels: chore, priority:medium, area:ci, effort:medium, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-22T07:13:14.693Z
---

# [Issue 604]: [[CHORE] Clean up stale code-scanning alerts and consolidate Trivy scan categories](https://github.com/vig-os/devcontainer/issues/604)

### Chore Type

CI / Build change

### Description

The **Security and quality** tab currently shows **564 open code-scanning alerts**, but a large share are **stale, orphaned, or duplicated** rather than genuine, actionable exposure. This issue tracks cleaning up the alert surface and consolidating the Trivy scan configuration so the count reflects reality.

**Findings (evaluated 2026-06-19):**

Totals: 983 alerts → **419 fixed**, **564 open**. Source is almost entirely **Trivy container-image CVE scans** (969 Trivy; 8 CodeQL all closed; 6 Scorecard). Open severity: 12 critical, 62 high, 260 medium, 201 low, 29 unknown.

| Category | Open | Source | State |
|---|---|---|---|
| `container-image-latest` | 236 | `security-scan.yml` nightly scan of GHCR `:latest` | **Live & accurate** (refreshed daily) |
| `container-image` | 313 | `ci.yml` Trivy on PR-built image | **Mostly stale** (last refresh 2026-06-11) |
| `container-image-scheduled` | 10 | a workflow that no longer exists | **Orphaned** (frozen 2026-03-30) |
| `supply-chain/*` (Scorecard) | 5 | Scorecard action | Config findings |

**Auto-close behaviour** (GitHub clears an alert when a later run of the *same category+tool+ref* omits it):

- ✅ `container-image-latest` auto-closes correctly (nightly refresh; 419 already-fixed prove the pipeline works).
- ⚠️ `container-image` will **not** reliably auto-close: `ci.yml` now uploads SARIF filtered to `severity: 'HIGH,CRITICAL'` only ([ci.yml#L314](../blob/main/.github/workflows/ci.yml#L314)), so its **191 low + 97 medium** alerts are zombies the current scan can no longer "see" to clear; it also runs only on `pull_request`, so `refs/heads/main` rarely gets a fresh upload.
- ❌ `container-image-scheduled` (10) can **never** auto-close — no workflow emits that category anymore.

**Actual actionable exposure is small:** of the open HIGH/CRITICAL, only **4 are fixable** (have an upstream patch); the other **67 are unfixed** (no vendor fix yet). The single live fixable HIGH/CRITICAL is already tracked by the nightly gate issue #602.

**Conclusion:** ~300 of the 564 are stale/orphaned duplicates from a superseded scan config, plus a long tail of unfixable CVEs. Cleaning up the dead categories and consolidating to one authoritative scan is the biggest lever.

### Acceptance Criteria

- [ ] The 10 orphaned `container-image-scheduled` alerts are dismissed (reason: `won't_fix` — orphaned category, no producing workflow).
- [ ] A decision is made and implemented for the stale `container-image` low/medium alerts: either (a) `container-image-latest` becomes the single authoritative scan and the ~292 stale `container-image` low/medium alerts are dismissed, or (b) `ci.yml` is restored to upload all-severity SARIF + reconcile on `main`.
- [ ] Scan categories in `ci.yml` / `security-scan.yml` are documented so future readers know which is authoritative (SSoT).
- [ ] The 5 Scorecard `supply-chain/*` findings are individually reviewed and either fixed or dismissed with rationale.
- [ ] After cleanup, the open alert count reflects only genuine, current exposure; a short note records the new baseline.
- [ ] TDD compliance (see .cursor/rules/tdd.mdc) — for any testable logic touched (e.g. workflow-helper scripts); pure workflow/YAML changes noted as non-testable.

### Implementation Notes

- Bulk-dismiss via REST: `gh api repos/:owner/:repo/code-scanning/alerts/<n> -X PATCH -f state=dismissed -f dismissed_reason="won't fix" -f dismissed_comment="..."`.
- Target files: `.github/workflows/ci.yml` (SARIF severity/trigger/category), `.github/workflows/security-scan.yml`, `.trivyignore`.
- Relates to discussion #109 (full security scan on every PR) — the category-consolidation decision overlaps with that thread.
- Does **not** cover remediating individual CVEs (tracked by the nightly gate issue #602).

### Related Issues

Relates to #602, #109

### Priority

Medium

### Changelog Category

Security

---

# [Comment #1]() by [c-vigo]()

_Posted on June 21, 2026 at 07:45 PM_

Executed on branch `chore/604-cleanup-scanning-alerts` (PR #605).

**Outcome — open alerts 564 → 237:**
- Track A: dismissed 10 orphaned `container-image-scheduled` alerts (no producer since 2026-03-30).
- Track B: `ci.yml` Trivy is now a gate-only step (SARIF upload removed); `container-image-latest` documented as SSoT; dismissed all 313 now-orphaned `container-image` alerts.
- Track C: dismissed all 5 Scorecard `supply-chain/*` findings with per-alert rationale.

**New baseline:** 237 open, all from the single authoritative nightly `container-image-latest` scan. Remaining genuinely-fixable HIGH/CRITICAL exposure continues to be tracked by the nightly gate issue #602.

