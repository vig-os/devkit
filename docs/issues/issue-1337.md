---
type: issue
state: closed
created: 2026-08-04T08:06:18Z
updated: 2026-08-04T10:03:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1337
comments: 1
labels: chore, priority:low, area:image, effort:small, area:docs, semver:patch, security
assignees: c-vigo
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:53.822Z
---

# [Issue 1337]: [chore(security): anchor exception-register expiries to a Wednesday grid](https://github.com/vig-os/devkit/issues/1337)

## Summary

Adopt a documented convention that every `Expiration:` date in the security
exception registers lands on a **Wednesday**, and re-schedule the current
entries onto that grid.

Expiry dates are currently picked ad hoc and land on arbitrary weekdays
(today: Sat, Mon ×4, Tue ×6, Wed ×1 across the three registers). Because
`check-expirations` runs in *every* PR CI (`ci.yml:390`), in pre-commit
(`.pre-commit-config.yaml:221`), in the release train (`release.yml:877`) and
in both nightly scan legs (`security-scan.yml:92`), a lapse blocks all work in
the repo — including PRs that have nothing to do with security. That has now
happened four times: #550 (16 Renovate PRs red at once), #1257, #1260, #1327.

## Why Wednesday and not Monday

The obvious anchor is Monday, to match the Renovate window
(`schedule: ["before 9am on monday"]`, `assets/workspace/.github/renovate-default.json`)
and this repo's existing Monday maintenance crons (codeql 02:15, ghcr-cleanup
04:00, unstable tracker 05:00, devkit-upgrade 06:00, all `* * 1`). But Monday
is too early, because of how the review data actually arrives:

1. `check-expirations` fails when `today > expiration` (`check_expirations.py:81`),
   so an entry dated `D` is valid *through* `D` and red from `D+1`.
2. **PR CI does not run vulnix** — `ci.yml:374-375` states the authoritative CVE
   gate is the nightly scan. So the Renovate pin-advance PR itself tells you
   nothing about which exceptions have gone dead.
3. The findings delta only exists after the pin merges to `dev` *and* the next
   nightly `security-scan` (05:00 UTC) runs against the new closure.

Chain: Renovate PR Mon ≤09:00 → merge Mon/Tue → first post-merge nightly Tue/Wed
05:00 → *then* the register can be reconciled.

| Expiry weekday | First red | Assessment |
|---|---|---|
| Sunday | Mon 05:00 | Worst — red before the week's Renovate PRs even open. This is exactly #550. |
| Monday | Tue 05:00 | Pin may not be merged yet; forces a blind extension. |
| Tuesday | Wed 05:00 | Workable, zero slack. |
| **Wednesday** | **Thu 05:00** | **Pin merged, one nightly has run on the new closure, two working days before the weekend.** |
| Thu–Sat | Fri–Sun | Unattended weekend red blocking every commit. |

Secondary benefit: reviews conclude "delete" more often instead of "extend".
#1327 found five entries that had been dead since the #1273 pin advance because
nobody had looked at the register with fresh findings in hand; podman, gawk and
libssh2 each carry two or three "Re-verified … retained" notes.

Third: the register already batches expiries by hand — the podman block says its
expiry was pushed 2026-08-06 → 2026-08-31 "to align with the libssh2 and unbound
blocks, so the register gets one combined re-review pass". A weekday grid makes
that automatic instead of a per-entry judgement call.

## Snapping rule

Nearest Wednesday, `|shift| <= 3 days`, prefer the shorter window on ties.
Never lengthen a window by more than 3 days; risk assessments are unchanged by
a snap and must not be silently re-opened by one.

## Re-scheduling of current exceptions

`.vulnixignore` (9 directives):

| Line | Current | Weekday | New | Shift | Block |
|---|---|---|---|---|---|
| 37 | 2027-06-23 | Wed | *(unchanged)* | 0 | Class 1 CPE mismatches (shellcheck, git) |
| 71 | 2026-08-15 | **Sat** | 2026-08-12 | −3 | glibc ×6 |
| 87 | 2026-08-31 | Mon | 2026-09-02 | +2 | zlib / sqlite ×2 / libmicrohttpd ×2 |
| 127 | 2026-08-17 | Mon | 2026-08-19 | +2 | fzf ×2 |
| 142 | 2026-09-01 | Tue | 2026-09-02 | +1 | libssh2 CVE-2026-58050 |
| 165 | 2026-08-31 | Mon | 2026-09-02 | +2 | podman CVE-2026-57231 |
| 212 | 2026-08-18 | Tue | 2026-08-19 | +1 | gawk ×4 — see note below |
| 258 | 2026-08-31 | Mon | 2026-09-02 | +2 | unbound ×5 |
| 305 | 2026-08-31 | Mon | 2026-09-02 | +2 | libssh2 ×3 (CVE-2026-6603x) |

`.trivyignore` (3 directives, lines 17 / 25 / 36): all 2026-09-01 (Tue) →
**2026-09-02** (+1).

`.github/dependency-review-allow.txt` (line 21): 2026-09-01 (Tue) →
**2026-09-02** (+1).

Notes:

- **The Saturday entry is the urgent one, independent of this convention.** The
  glibc block expires 2026-08-15 (Sat), so it goes red **Sunday 2026-08-16 at
  05:00 UTC** and blocks every commit, PR and release until renewed. Snapping it
  back to 08-12 shortens the window by 3 days and moves the failure to a Thursday.
- **The gawk block (line 212) may disappear first.** #1328 reports gawk 5.4.1 has
  landed in `nixos-26.05`; if that pin advance lands before this work, drop the
  block entirely rather than re-dating it.
- **Eight of thirteen directives converge on 2026-09-02.** That is the intended
  combined-review pass, but it does mean one stalled review blocks the whole
  register. De-clustering should happen at each block's *next* renewal by picking
  different week-multiples — not now, since spreading them today would either
  extend windows past the ±3 cap or pull unrelated reviews forward.

## Out of scope (deliberate)

**No change to `check_expirations.py`.** The validator is scaffolded into every
consumer repo (`assets/workspace/.pre-commit-config.yaml:133`), and consumers can
override their Renovate schedule. Hard-enforcing a weekday there would impose
devkit's cadence org-wide and add a *new* failure class to the very tool whose
failures this issue is trying to reduce. This stays a documented convention
enforced by review. If enforcement is ever wanted, it must be warning-only and
opt-in — a separate issue.

## Acceptance criteria

- [ ] `docs/CONTAINER_SECURITY.md` §5 (Exception registers) documents the
      Wednesday convention: the anchor, the snapping rule, the reason (Renovate
      Monday window → merge → first post-merge nightly → weekend avoidance), and
      that it is a convention, not a validated constraint.
- [ ] The doc states the dependency on the Renovate `schedule` explicitly, so the
      rationale does not silently rot if that preset changes.
- [ ] No second copy of the convention: `SECURITY.md` already links to
      `docs/CONTAINER_SECURITY.md` and must keep linking, not restating (SSoT).
- [ ] All 12 non-conforming `Expiration:` directives re-dated per the table
      above; the 2027-06-23 directive is left untouched.
- [ ] Each re-dated block records that the date was snapped to the Wednesday grid
      and that its **risk assessment is unchanged** — the IEC 62304 register must
      not read as if the acceptance was silently re-opened.
- [ ] `uv run check-expirations .trivyignore .vulnixignore` and
      `uv run check-expirations .github/dependency-review-allow.txt` pass.
- [ ] `CHANGELOG.md` `## Unreleased` entry under **Changed**.
- [ ] `check_expirations.py` unchanged.

## Related issues

Related to #550, #1257, #1260, #1327 (lapse incidents), #1273 / #1328 (pin
advance as the remediation lever), #1237 (dev-ref nightly lane), #637, #512.

## Priority / effort

Low priority, small effort — but the glibc Saturday entry needs handling before
2026-08-16 regardless of when the convention itself is adopted.

Changelog category: Changed.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 10:02 AM_

Done on dev via PR #1338 (merge 698b04f7): expiry grid documented in docs/CONTAINER_SECURITY.md and all 12 non-conforming dates snapped to Wednesdays. Ships with 1.6.0.

