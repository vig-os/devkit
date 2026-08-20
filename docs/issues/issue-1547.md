---
type: issue
state: closed
created: 2026-08-20T06:49:44Z
updated: 2026-08-20T07:05:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1547
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch, security
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-20T12:22:21.178Z
---

# [Issue 1547]: [[BUG] fzf vulnix exception block expired 2026-08-19 — check-expirations reds every branch and both nightly lanes](https://github.com/vig-os/devkit/issues/1547)

### Description

The fzf exception block in `.vulnixignore` carries `Expiration: 2026-08-19` and
expired on the Wednesday grid date (#1337). `check-expirations` is
`enable = true` in the flake hook set (`nix/hooks.nix:816`), so it runs inside
the `pre-commit` derivation Tier 0 `nix-fast-build` evaluates — **every branch
is red on `project-checks`** — and the nightly `Scheduled Security Scan` failed
on **both** lanes this morning
([run 32335643087](https://github.com/vig-os/devkit/actions/runs/32335643087),
05:27 UTC, 59s), aborting at the *first* step, before vulnix ever ran:

```
::error::Expired security exceptions — review and renew or remove:
::error::  - .vulnixignore: CVE-2026-53432 (expired 2026-08-19)
::error::  - .vulnixignore: CVE-2026-53433 (expired 2026-08-19)
```

Two CVEs are affected, both against `fzf 0.72.0` (in-closure via zoxide):
`CVE-2026-53432`, `CVE-2026-53433`.

### Evidence — nothing is droppable this cycle

Both are **still live findings** against the current closure. From the last
green nightly scan's `vulnix-findings.json`
([run 32219442917](https://github.com/vig-os/devkit/actions/runs/32219442917),
2026-08-19, pinned rev `531670d871c0`):

| CVE | CVSS v3 | Still reported against `fzf-0.72.0` |
|-----|---------|-------------------------------------|
| CVE-2026-53432 | 7.5 | yes |
| CVE-2026-53433 | 7.5 | yes |

The "advance the rev" lever has nowhere to land. Verified 2026-08-20:

- the pinned closure still evaluates to `fzf 0.72.0`
  (`nix eval …inputs.nixpkgs…fzf.version` on rev `531670d8`)
- `nixos-26.05`, `release-26.05` **and** `staging-26.05` all still ship
  `0.72.0`; only `master` / `nixpkgs-unstable` carry `0.74.3`
  (`fzf: 0.74.2 -> 0.74.3` = NixOS/nixpkgs#553573, merged 2026-08-17)
- no 26.05 backport PR is open

The 2026-07-14 risk assessment is unchanged and stands: `CVE-2026-53432` is a
`FuzzyMatchV2` integer-overflow panic on **32-bit Go builds only** (this image
is 64-bit) and `CVE-2026-53433` is CPU-DoS of fzf's **opt-in** localhost
`--listen` server, never started here. Availability-only either way.

### Register reconciliation

All 28 register entries were reconciled against the 08-19 findings: 25
HIGH/CRITICAL findings, **zero unexcepted** — renewing this one block is
sufficient to turn both lanes green. Three entries (`CVE-2022-30947`,
`CVE-2022-36882`, `CVE-2022-36883` — the Jenkins Git-plugin CPE mismatches,
expiry 2027-06-23) are no longer reported at all and become drop candidates at
their own review date; out of scope here.

### Expected Behavior

`check-expirations` passes; the nightly scan reaches vulnix and the gate on both
lanes.

### Actual Behavior

Both nightly lanes and every branch's `project-checks` fail on the expired
block.

### Proposed fix

Renew the block `2026-08-19 -> 2026-09-02` — the shared grid date the rest of
the register already sits on, so the whole register comes up for review in one
pass — with the evidence above recorded as a renewed risk acceptance, not a date
bump.

Note: `main` and `dev` carry an identical register, so the `main` lane stays red
nightly until the 1.11.0 train merges `dev` into `main`.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 20, 2026 at 07:05 AM_

Fixed on `dev` in #1549 (merge `227dedc0`) — the fzf block is renewed to the shared `2026-09-02` grid date, so `check-expirations` passes on every branch and tonight's `dev` lane reaches the vulnix gate again.

```
$ uv run check-expirations .trivyignore .vulnixignore
Validated 32 exception(s) across 2 file(s)
```

The `main` lane stays red nightly until the 1.11.0 train merges `dev` into `main` — `main` carries the same expired register today. Closing manually: a dev-targeted PR's `Closes` reference does not auto-close (main-only).

The reporting hole this exposed — a pre-gate failure files no tracking issue at all — is #1548.

