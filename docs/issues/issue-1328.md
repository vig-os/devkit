---
type: issue
state: closed
created: 2026-08-04T06:38:03Z
updated: 2026-08-04T10:03:14Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1328
comments: 1
labels: chore, priority:medium, area:image, effort:medium, semver:patch, security
assignees: c-vigo
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:55.345Z
---

# [Issue 1328]: [Advance pinned nixpkgs rev to drop the gawk exception block (5.4.1 has landed in nixos-26.05)](https://github.com/vig-os/devkit/issues/1328)

## Problem

The gawk `.vulnixignore` block (CVE-2026-40467 / -40468 / -40469 / -40553, expires
**2026-08-18**) has been renewed twice — #1240 and again at the #1273 pin advance —
because gawk 5.4.1 sat in nixpkgs *staging* and the "advance the rev" lever had
nowhere to land.

Verified 2026-08-04: **`nixos-26.05` now ships gawk 5.4.1**, while the image pin
(`8623c4c2`, 2026-07-26) still ships **5.4.0**. The lever is available for the first
time, so the block can be dropped rather than renewed a third time before it lapses.

## Scope

- Advance the pinned `nixpkgs` input (`nixos-26.05`) in `flake.lock`.
- Rebuild and re-scan; confirm the closure ships gawk 5.4.1 and that the four gawk
  CVEs drop out of the vulnix findings.
- Remove the gawk block from `.vulnixignore` (do **not** just extend the expiry).
- Re-verify the rest of the register against the new rev and prune anything else the
  bump fixes — at the last pin advance the prune was missed, which is part of what
  #1327 is cleaning up (five entries were dead but still listed).

Note that gawk is a stdenv member, so this is a mass rebuild — expect a long image
build and a cachix repopulation.

## Context

- The register-hygiene pass that this follows: #1327 (also #1322 / #1323).
- Previous pin advance: #1273. Previous gawk renewals: #1071, #1240.
- Still *not* fixed in `nixos-26.05` HEAD as of 2026-08-04, so they stay exceptions
  either way: libssh2 1.11.1, unbound 1.25.1, fzf 0.72.0, podman 5.8.2.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 10:01 AM_

Done in #1340, merged to `dev` as `04f955f0`.

The pin advanced from nixos-26.05 @ `8623c4c2` (2026-07-26) to @ `531670d8` (2026-08-03) — the first pinned-channel rev shipping **gawk 5.4.1** — and the gawk block was **removed, not renewed** a third time.

**Verification** (both closures built and scanned locally with the same command `security-scan.yml` runs):

| | old pin `8623c4c2` | new pin `531670d8` |
|---|---|---|
| gawk | 5.4.0 | **5.4.1** |
| unique CVEs | 59 | 55 |
| finding groups | 18 | 16 |

Dropped: `CVE-2026-40467`, `CVE-2026-40468`, `CVE-2026-40469`, `CVE-2026-40553` — the **only** delta. Nothing new appeared.

- `vulnix-gate` → `No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 27 exception(s) applied` (was 31)
- `check-expirations` → `Validated 27 exception(s)`
- PR CI green 14/14, including Build Container Image, Image Tests, Integration Tests and Security Scan — the stdenv mass rebuild is sound.

**Register re-verified against the new rev** per the scope: nothing else became droppable. fzf (0.72.0), libssh2 (1.11.1, still carrying no 6603x patch), unbound (1.25.1) and podman (5.8.2) are all unchanged, so those blocks are retained with a 2026-08-04 re-verification note. The prune that #1327 was cleaning up did not recur — the only register entries not corresponding to a live finding remain the three Class-1 Jenkins-Git CPE collisions, deliberately kept on their yearly re-check.

As predicted in the issue, libssh2 1.11.1, unbound 1.25.1, fzf 0.72.0 and podman 5.8.2 stay as exceptions.

