---
type: issue
state: closed
created: 2026-07-23T08:25:56Z
updated: 2026-07-23T16:00:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1257
comments: 2
labels: security, security-scan
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-24T05:27:30.012Z
---

# [Issue 1257]: [Renew lapsed curl + openssh .vulnixignore exceptions (nightly scan red)](https://github.com/vig-os/devkit/issues/1257)

## Problem

The nightly **Scheduled Security Scan** went red on 2026-07-23 ([run 29988472212](https://github.com/vig-os/devkit/actions/runs/29988472212)), failing at the first gate step `Validate .vulnixignore exception expirations` (`uv run check-expirations .vulnixignore`, exit 1).

**Root cause:** the 18-CVE **curl 8.20.0** advisory batch (`.vulnixignore`, `Expiration: 2026-07-22`) lapsed. Not a new/regressed vulnerability — a time-boxed risk acceptance that expired. Affected: `CVE-2026-10536 -11856 -8925 -9079 -11564 -8924 -8926 -8927 -8286 -11352 -11586 -12064 -8932 -9545 -9546 -9547 -9080`.

The **openssh** block (`CVE-2026-60002`, `Expiration: 2026-07-24`) lapses tomorrow and is renewed in the same pass to avoid an immediate re-red.

## Remediation lever

- **curl:** 8.21.0 (2026-06-24) fixes the whole batch and is in `nixpkgs-unstable`, but the image pin (`nixos-26.05`) still ships **8.20.0** — verified. Rev-advance has nowhere to land in the pinned channel.
- **openssh:** fixed in 10.4p1 (2026-07-06); pinned `nixos-26.05` still ships **10.3p1** — verified. No rev-advance target either.

So both blocks are **renewed with a fresh short expiry** (the #1240 gawk-extension pattern), pending backport propagation to `nixos-26.05`. Flip each to a pin bump the moment the fixed version lands in the pinned channel.

## Scope

- Renew the curl block expiry with a dated re-verification note.
- Renew the openssh block expiry with a dated re-verification note.
- Fold into the promote-ready 1.4.1 train (base `release/1.4.1`), so the fix reaches `main` at promote and the release-branch scan stays green.

## Out of scope (separate follow-up)

The tracking-issue automation did not fire because its guard keys on `vulnix-gate.outcome == 'failure'`, but the run died at the earlier `check-expirations` step. Widening that guard is a separate issue.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 11:00 AM_

Update (2026-07-23, after PR #1258 merged): the pinned channel has now advanced past the verification in this issue's description. At `nixos-26.05` rev `fd1462031fdee08f65fd0b4c6b64e22239a77870` (channel tip as of today, lastModified 2026-07-23):

- `curl.version` = **8.21.0** (fixes the whole 17-CVE batch)
- `openssh.version` = **10.4p1** (fixes CVE-2026-60002)

(verified via `nix eval --raw github:NixOS/nixpkgs/nixos-26.05#curl.version` / `#openssh.version`; the pinned rev `34268251` still ships 8.20.0/10.3p1.)

Per this register's protocol the flip-to-rev-advance now has a landing spot: bump the `nixpkgs` pin and drop both blocks (plus re-check the podman `CVE-2026-57231` and gawk #1240 entries at the new rev while at it). Given the renewed expiries run to 2026-08-15 and the 1.4.1 train is promote-ready, the pin bump is best done as a follow-up on `dev` after promote rather than folded into the train.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 23, 2026 at 04:00 PM_

Shipped in [1.4.1](https://github.com/vig-os/devkit/releases/tag/1.4.1) (promoted 2026-07-23). Reminder from the update above: `nixos-26.05` now carries curl 8.21.0 + openssh 10.4p1, so the flip-to-rev-advance (pin bump on `dev` + drop both blocks, re-check podman/gawk entries) is the follow-up before the 2026-08-15 expiry.

