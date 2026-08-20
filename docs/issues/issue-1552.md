---
type: issue
state: closed
created: 2026-08-20T08:36:32Z
updated: 2026-08-20T10:07:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1552
comments: 2
labels: feature, priority:high, area:ci, effort:medium, semver:minor, security
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-20T12:22:20.662Z
---

# [Issue 1552]: [[FEATURE] Warn one week before a security exception expires instead of failing every branch the day after](https://github.com/vig-os/devkit/issues/1552)

### Description

Security exception expiries currently surface only as a **hard failure on the
day after**. `check-expirations` fails when `today > expiration`, and it runs in
PR CI (`ci.yml:441`, `ci.yml:524`), as the first step of both nightly
`security-scan.yml` lanes (`:98`), and in the release train (`release.yml:906`).
One lapsed block therefore reds every open branch, both scan lanes and the
release path at once, with zero prior warning.

Add an **advance notice**: when an exception is within **7 days** of expiring,
open a deduplicated tracking issue so the review is scheduled work instead of a
surprise outage.

### Problem Statement

Three incidents in two months, each the same shape — an expiry fired, CI went
red everywhere, and the fix was reactive:

- [#1260](https://github.com/vig-os/devkit/issues/1260) — curl batch,
  `.trivyignore`, "now blocks all CI"
- [#1481](https://github.com/vig-os/devkit/issues/1481) — glibc block,
  "reds every branch"
- [#1547](https://github.com/vig-os/devkit/issues/1547) — fzf block, reddened
  every branch **and** both nightly lanes, and (via
  [#1548](https://github.com/vig-os/devkit/issues/1548)) did it silently

None of these were surprises in substance — every date was chosen deliberately
by a human weeks earlier. The information existed; nothing surfaced it.

### Proposed Solution

**1. `check-expirations --warn-days N` (+ `--json`)** in
`packages/vig-utils/src/vig_utils/check_expirations.py`.

- Default behaviour byte-identical, so no existing call site changes.
- `--warn-days N` emits `::warning::` annotations for entries expiring within N
  days and exits `0`; entries already expired still exit `1` as today.
- `--json` emits `{"expired": [...], "expiring": [{"id", "file", "expiration",
  "days_left"}]}` so a workflow can build an issue body without re-parsing the
  register format. The validator stays the single parser — no second
  implementation of the `Expiration:` grammar.

**2. A third issue class in `security-scan.yml`**, not a new workflow. That job
already carries the `main`/`dev` matrix, `issues: write`, the `security-scan`
label bootstrap and the ref-distinct dedup pattern from #1548; a standalone
workflow would duplicate all of it and still need `setup-env` for `uv run`. The
new step goes **before** the hard validation step, so an already-red register
still reports what is coming next.

**3. One issue per (ref x expiry date)**, e.g.
`Security exception register (dev): exceptions expire 2026-09-02`. This dedups
naturally, maps 1:1 to a single review pass, and gives staggered dates their own
issues — which reinforces the "stagger across weeks" rule in
`docs/CONTAINER_SECURITY.md`.

**4. Cover all three registers** — `.vulnixignore`, `.trivyignore` and
`.github/dependency-review-allow.txt`. The nightly scan validates only
`.vulnixignore` today, but the other two red every branch just as hard (#1260
was a `.trivyignore` case).

### Why 7 days

Not arbitrary — it is exactly one grid period. `docs/CONTAINER_SECURITY.md`
puts every `Expiration:` on a **Wednesday** so the entry turns red on the
Thursday *after* the week's Renovate `nixpkgs` bump and the first nightly
findings delta. A 7-day lead makes the notice land on a Wednesday too, one full
Renovate cycle ahead: notice Wed, bump merges Mon/Tue, nightly delta Tue/Wed,
act Wed, red Thu.

- 3 days would fire on a Sunday, into an unattended weekend.
- 14 days would fire *before* the previous cycle's data existed, inviting
  exactly the blind date-bump the grid is designed to prevent.

### Alternatives Considered

- **A dedicated `exception-expiry-watch.yml`.** Cheaper per run (no Nix, no
  closure build) and survives a broken scan, but duplicates the matrix, dedup,
  labels and `setup-env` block for a step that is ~10 lines inside the job that
  already owns this signal. Rejected on DRY/minimal-diff grounds; revisit if the
  nightly scan's reliability becomes the binding constraint.
- **`--warn-days` in PR CI only** (yellow annotation, no issue). Cheap and worth
  adding alongside, but PR annotations reach whoever happens to open that run —
  not the person who owns the register. It is not a substitute for a scheduled
  notice.
- **Do nothing; the expiry firing *is* the design.** True, and this must not
  weaken it (see Notes) — but a notice ahead of a hard gate does not remove the
  gate.

### Notes

**Guard against the blind-extension failure mode.** The Wednesday grid exists so
that entries can be **deleted** rather than extended, once the week's findings
delta shows what the pin advance fixed. An early warning could produce blind
date-bumps a week ahead of that data. The issue body must therefore say
explicitly: *check the latest nightly findings delta first; delete what the pin
advance cleared; a renewal is a re-verification, not a date bump* — the standard
this register already holds itself to (see the #1547 and #1481 block notes).

**Out of scope: the scaffold.** Consumers get the `check-expirations` pre-commit
hook but ship no registers and no `security-scan.yml`, so there is nothing to
warn about. `--warn-days` is available to them through the pinned utility if
they ever add one.

**Related:** the register currently has 29 of 33 entries on a single date — see
the companion staggering issue. This feature gives notice of that cliff; it does
not flatten it.

### Impact

- Backward compatible: `check-expirations` keeps its current CLI contract and
  exit codes; only new opt-in flags are added.
- Benefits anyone whose branch would otherwise go red for a reason unrelated to
  their change.

### Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on August 20, 2026 at 08:36 AM_

Companion: #1553 staggers the `2026-09-02` register cliff (29 of 33 entries on one date). Disjoint scopes — this issue is tooling (`check-expirations` + `security-scan.yml`), #1553 touches only the `Expiration:` directives in the registers. Expect a `CHANGELOG.md` overlap only, which union-merges.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 20, 2026 at 10:07 AM_

Merged to `dev` in #1555 (`e4726f1d`).

Verified on `dev` after both this and #1553 landed, against the real (now staggered) registers:

| Injected date | Result |
|---|---|
| 2026-08-20 | 0 expiring, exit 0 |
| 2026-08-26 | 1 expiring (`2026-09-02`), exit 0 — notice fires one grid period ahead |
| 2026-09-09 | 9 expiring across `2026-09-09`/`2026-09-16`, exit 1 on the already-expired entry |

Default stdout/stderr/exit are byte-identical to the pre-change implementation, so the four existing call sites are unaffected.

Closing manually — a dev-targeted PR's `Closes` does not auto-close (main-only).

