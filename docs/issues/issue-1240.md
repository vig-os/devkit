---
type: issue
state: closed
created: 2026-07-21T11:15:23Z
updated: 2026-07-21T11:58:53Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1240
comments: 1
labels: chore, security
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:37.346Z
---

# [Issue 1240]: [Extend gawk CVE exception expiry — gawk 5.4.1 still not in nixos-26.05](https://github.com/vig-os/devkit/issues/1240)

## Summary

The short-dated `.vulnixignore` exception for the gawk 5.4.0 CERT-PL CVE batch
(`CVE-2026-40467`, `-40468`, `-40469`, `-40553`) added in #1071 / #1072 for the
1.2.0 release expires **2026-07-28**. The planned remediation was to flip to a
nixpkgs rev-advance once gawk 5.4.1 lands in the pinned `nixos-26.05` channel —
but that has not happened yet, so the exception must be extended.

## Upstream status (re-verified 2026-07-21 via raw.githubusercontent.com)

| nixpkgs branch | `pkgs/tools/text/gawk/default.nix` version |
|----------------|--------------------------------------------|
| `nixos-26.05` (pinned channel) | `5.4.0` — still vulnerable |
| `release-26.05` | `5.4.0` — still vulnerable |
| `staging` | `5.4.1` — fixed |

The fix (gawk 5.4.1, `NixOS/nixpkgs#540158`) merged to `staging` on 2026-07-12.
gawk is a stdenv mass-rebuild, so it must traverse the `staging` -> `staging-next`
-> release-branch pipeline before reaching `nixos-26.05`. As of today it has NOT
propagated, so the "advance the rev" lever still has nowhere to land.

## Action

Extend the exception's `Expiration:` to **2026-08-18** (a further short-dated
window) to force a near-term re-check while the staging merge continues to
propagate. Risk posture is unchanged from the #1071 triage: gawk processes only
developer/CI-chosen awk programs and inputs in the single-user dev model, and
the readdir-extension CVE requires the opt-in `-l readdir` path.

## Follow-up

Flip to the nixpkgs rev-advance (and drop this exception) as soon as 5.4.1
reaches `nixos-26.05`.

Refs: #1071, #1072

---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:58 AM_

Fixed on dev via PR #1241 (merged): .vulnixignore gawk exception expiry extended 2026-07-28 → 2026-08-18. Upstream re-verified 2026-07-21: gawk still 5.4.0 on nixos-26.05 and release-26.05; 5.4.1 only in staging (NixOS/nixpkgs#540158). Flip to a rev-advance once it lands. Ships with 1.4.1.

