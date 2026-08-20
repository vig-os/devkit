---
type: issue
state: closed
created: 2026-08-20T08:36:34Z
updated: 2026-08-20T10:07:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1553
comments: 2
labels: chore, priority:high, area:ci, effort:small, semver:patch, security
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-20T12:22:20.384Z
---

# [Issue 1553]: [[CHORE] Stagger the 2026-09-02 exception-register cliff — 29 of 33 entries expire on one date](https://github.com/vig-os/devkit/issues/1553)

### Description

29 of the 33 live security exception entries expire on the **same day**,
`2026-09-02`, across all three registers:

| Register | `2026-09-02` | `2027-06-23` |
|---|---:|---:|
| `.vulnixignore` | 24 | 4 |
| `.trivyignore` | 4 | — |
| `.github/dependency-review-allow.txt` | 1 | — |
| **Total** | **29** | **4** |

On `2026-09-03` the entire register goes red at once: every open PR's CI, both
nightly `security-scan` lanes, and the release train. Spread the renewals across
several Wednesdays so no single stalled review can do that.

### Motivation

This directly violates the repo's own rule in
`docs/CONTAINER_SECURITY.md` ("Stagger across weeks, not weekdays"):

> Sharing one date gives the register a single combined re-review pass, which is
> the intent; but every block on the *same* Wednesday means one stalled review
> blocks the whole register. Spread renewals over different Wednesdays by
> choosing different week-multiples.

The cliff was built incrementally and in good faith — #1337 snapped the register
onto the Wednesday grid, then #1481, #1327/#1328, #1386 and most recently #1547
each renewed "onto the shared `2026-09-02` grid date so the whole register is
reviewed in one pass". Each step was locally reasonable; the aggregate is a
single point of failure covering 88% of the register.

For scale: #1547 was **one** block (2 CVEs) and it reddened every branch plus
both nightly lanes. This is 29 entries in 8 blocks across 3 files.

### Scope

Re-date the `Expiration:` directives only, onto distinct Wednesdays, and record
the re-dating in each block's note. Suggested grouping by remediation lever, so
each pass has a coherent question to answer:

- **`.vulnixignore` glibc block** (6 CVEs) — no rev-advance lever exists
  (advisories scope the defect through 2.43); longest window.
- **`.vulnixignore` libssh2 blocks** (CVE-2026-58050 + the 6603x batch, 5 CVEs)
  — gated on the nixpkgs `staging-26.05` backport reaching the pinned channel.
- **`.vulnixignore` unbound block** (5 CVEs) — gated on 1.25.2 reaching
  `nixos-26.05`.
- **`.vulnixignore` podman / fzf / low-reachability blocks** — each tracks its
  own upstream.
- **`.trivyignore` + `.github/dependency-review-allow.txt`** (5 entries) — a
  separate register with a separate review.

Pick week-multiples so no two groups land on the same Wednesday, and keep every
window at or shorter than the current `2026-09-02` where the risk assessment
does not justify extending. Apply the snapping rule from
`docs/CONTAINER_SECURITY.md` (nearest Wednesday, shift <= 3 days).

### Non-goals

- **No risk assessments are re-opened.** As with the #1337 snap, a re-date is a
  scheduling adjustment only: every rationale stands exactly as written, and no
  entry is added or removed here. If a block turns out to be droppable against
  the current pin, that is a separate change with its own evidence.
- **No documentation change.** The staggering rule is already documented; this
  issue brings the register into line with it.
- **No tooling change.** The advance-warning feature is tracked separately; it
  gives notice of a cliff, it does not flatten one.

### Acceptance

- No Wednesday carries more than one block across the three registers.
- `uv run check-expirations .trivyignore .vulnixignore
  .github/dependency-review-allow.txt` passes.
- Every re-dated block carries a dated note recording the re-dating and citing
  this issue, in the style the register already uses.

### Changelog Category

Changed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 20, 2026 at 08:36 AM_

Companion: #1552 adds the 7-day advance warning. That feature gives notice of this cliff; it does not flatten it, which is why the two are tracked separately. Disjoint scopes — #1552 is tooling only, this one touches only the `Expiration:` directives.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 20, 2026 at 10:07 AM_

Merged to `dev` in #1554 (`6632d631`).

Verified independently after merge: the parsed entry set is identical to pre-change (nothing added or removed), the only deleted lines are the 10 old `Expiration:` directives plus one header comment that was extended rather than rewritten, and all 12 blocks now sit on 12 distinct Wednesdays with no date shared across the three registers.

The cliff is cleared well before `2026-09-02`. That date now carries the podman block alone, as the deliberate anchor.

Closing manually — a dev-targeted PR's `Closes` does not auto-close (main-only).

