---
type: issue
state: closed
created: 2026-08-13T07:48:27Z
updated: 2026-08-13T08:32:24Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1481
comments: 1
labels: bug, area:ci
assignees: c-vigo
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:09.789Z
---

# [Issue 1481]: [[BUG] glibc vulnix exception block expired 2026-08-12 — check-expirations reds every branch](https://github.com/vig-os/devkit/issues/1481)

### Description

The glibc exception block in `.vulnixignore` carries `Expiration: 2026-08-12`
(line 84) and expired yesterday. `check-expirations` is `enable = true` in the
flake hook set (`nix/hooks.nix:749`), so it runs inside the `pre-commit`
derivation that Tier 0 `nix-fast-build` evaluates — **every branch is red on
`project-checks`**, and the nightly `Scheduled Security Scan` has been failing on
both `dev` and `main` since this morning.

Six CVEs are affected:

```
CVE-2025-15281, CVE-2026-4046, CVE-2026-4437,
CVE-2026-5435, CVE-2026-5450, CVE-2026-5928
```

### Evidence — nothing is droppable this cycle

Unlike the gawk block (#1328, dropped outright after the pin advance), every one
of these is **still a live finding** against the current closure. From the last
green nightly scan's `vulnix-findings.json`
([run 31569093850](https://github.com/vig-os/devkit/actions/runs/31569093850),
2026-08-12, the pinned rev `531670d871c0`):

| CVE | CVSS v3 | Still reported against `glibc-2.42-67` |
|-----|---------|----------------------------------------|
| CVE-2026-5450 | 9.8 | yes |
| CVE-2025-15281 | 7.5 | yes |
| CVE-2026-4437 | 7.5 | yes |
| CVE-2026-4046 | 7.5 | yes |
| CVE-2026-5928 | 7.5 | yes |
| CVE-2026-5435 | 7.3 | yes |

The same scan reports two further glibc CVEs that are **not** in the register and
do not need to be — both are below the gate's 7.0 threshold: CVE-2026-4438 (5.4)
and CVE-2026-6238 (6.5). `vulnix-gate` passed that run on 28 applied exceptions.

The "advance the rev" lever has nowhere to land: the CVE texts scope the defects
to *"version 2.34 to version 2.43"* and *"version 2.7 to version 2.43"*, so
glibc 2.43 is itself affected — remediation would have to arrive as backported
patches, not a version bump.

### Expected Behavior

`check-expirations` passes; CI is green on branches whose content is fine.

### Actual Behavior

```
Expired security exceptions — review and renew or remove:
  - .vulnixignore: CVE-2025-15281 (expired 2026-08-12)
  ... (6 entries)
```

`tests/test_flake_checks.py::test_flake_check_succeeds` fails for the same
reason, since it shells out to `nix flake check`.

### Possible Solution

Renew the block to **2026-09-02**, the Wednesday grid date the register's five
other blocks already share (#1337), so the whole register comes up for review in
one pass on the next cycle. Record the re-verification evidence above in the
block's note, per the #1328 precedent — a renewal is a fresh risk acceptance,
not a date bump.

The deployment context is unchanged and is what the acceptance rests on: an
interactive, single-user dev container with no untrusted network services, where
these glibc vectors need crafted local input.

### Changelog Category

Security

Refs: #637, #1328, #1337, #1386

---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 08:32 AM_

Fixed on `dev` via #1482 (merged as `c4a5e55e`).

Closing manually: a PR merged into `dev` does not auto-close its issue in this repo — the `Closes` keyword only fires for PRs targeting the default branch. Ships in the next release train.

