---
type: issue
state: closed
created: 2026-08-04T06:37:47Z
updated: 2026-08-04T10:03:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1327
comments: 1
labels: bug, priority:high, area:image, effort:small, semver:patch, security, security-scan
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:56.061Z
---

# [Issue 1327]: [Reconcile .vulnixignore: new libssh2 CVE batch blocks the gate, two exceptions lapsed 2026-08-03](https://github.com/vig-os/devkit/issues/1327)

## Problem

The nightly **Scheduled Security Scan** has been red on **both refs** since 2026-07-31
([run 30614074169](https://github.com/vig-os/devkit/actions/runs/30614074169) → #1322 dev / #1323 main),
and again on 08-01, 08-02 and
[08-03](https://github.com/vig-os/devkit/actions/runs/30797351489). `dev` and `main`
share the same nixpkgs pin (`nixos-26.05` @ `8623c4c2`), so the closures — and the
findings — are identical; one register fix covers both.

Two independent problems are in play:

### 1. Gate: three new libssh2 CVEs (blocking)

`vulnix-gate` reports exactly **3 unexcepted findings**, all in `libssh2 1.11.1`,
all CVSS v3 **7.5 HIGH**, all disclosed 2026-07-24 and surfaced in the vulnix feed
on 07-30/31. Diffing the findings against the last green run (30523258723,
2026-07-30) confirms these three are the *only* change — nothing else regressed.

| CVE | Flaw | Trigger |
|-----|------|---------|
| [CVE-2026-66033](https://nvd.nist.gov/vuln/detail/CVE-2026-66033) | pre-auth integer underflow in `ssh2_cipher_crypt()` (`src/openssl.c`) → OOB read + `memcpy` with a near-`SIZE_MAX` length → client crash | malicious server negotiating AES-GCM |
| [CVE-2026-66034](https://nvd.nist.gov/vuln/detail/CVE-2026-66034) | publickey subsystem: server-supplied unsafe length → heap OOB read; error path frees an uninitialized pointer | malicious server |
| [CVE-2026-66035](https://nvd.nist.gov/vuln/detail/CVE-2026-66035) | pre-auth heap buffer overflow in `fullpacket()` (`src/transport.c`) | malicious server, undersized packet during EtM negotiation |

All three are **client-side, malicious-server-required** — the same reachability
class as the already-accepted CVE-2026-58050. `libssh2` enters the closure only as
curl's scp/sftp backend (git uses openssh); nothing here initiates libssh2 SSH
sessions, so exploitation requires a developer pointing curl at a hostile SSH server.

### 2. Register: two exceptions lapsed 2026-08-03 (repo-wide CI red)

`uv run check-expirations .trivyignore .vulnixignore` exits 1 **as of today**:

```
- .vulnixignore: CVE-2026-55200 (expired 2026-08-03)
- .vulnixignore: CVE-2026-56123 (expired 2026-08-03)
```

That is the `check-expirations` pre-commit hook and `ci.yml:390` — so *every* PR and
branch is red until it is fixed, not just the nightly. And per the follow-up noted in
#1257, tonight's scheduled run will die at the earlier `check-expirations` step, whose
failure does **not** fire the tracking-issue automation (it guards on
`vulnix-gate.outcome == 'failure'`), so the nightly would go quiet while still red.

## Remediation lever

**libssh2 — no rev-advance available.** Upstream has fixes in git (commit
`a2ed82d4`, [libssh2#2401](https://github.com/libssh2/libssh2/pull/2401)) but **no
release since 1.11.1 (Oct 2024)**. In nixpkgs,
[#547491](https://github.com/NixOS/nixpkgs/pull/547491) ("libssh2: apply debian
patches for CVE-2026-6603[2345]", tracker
[#545668](https://github.com/NixOS/nixpkgs/issues/545668)) is **open against
`staging`**, not merged, explicitly needs a later backport to `release-26.05`, and is
gated behind nixpkgs#546446. Verified 2026-08-04: `nixos-26.05` HEAD still ships
`libssh2 1.11.1` with no 6603x patch. So a time-boxed exception is the only lever,
per `docs/CONTAINER_SECURITY.md`.

## Register reconciliation (all entries checked 2026-08-04)

Every entry was diffed against the current findings and against the package state at
the pinned rev. **Five entries are dead** — each provably fixed by the 2026-07-26 pin
advance (#1273), where the prune was missed:

| Entry | Package | Why it is dead at the pinned rev |
|-------|---------|----------------------------------|
| CVE-2026-55200 | libssh2 | nixpkgs applies `CVE-2026-55200.patch` (commit `f6ae2642`, nixos-26.05, 2026-07-01 — *in* the pin). vulnix credits CVE-named `patches` entries, so it no longer reports it. The #1273 note claiming "no fix in the pinned channel" was already stale when written. |
| CVE-2026-56123 | socat | pin ships **1.8.1.3** ≥ the 1.8.1.2 fix |
| CVE-2026-10846 | ldns | pin ships **1.9.2** (register says 1.9.0) |
| CVE-2026-41992 | gzip | pin applies `CVE-2026-41992.patch` |
| CVE-2026-11979 | libxml2 | pin applies `CVE-2026-11979.patch` |

Still live and correctly retained: glibc block (6, exp 08-15), zlib/sqlite/libmicrohttpd
(exp 08-31), fzf (exp 08-17, channel HEAD still 0.72.0), libssh2 CVE-2026-58050
(exp 09-01), gawk batch (4, exp 08-18), unbound batch (5, exp 08-31, channel HEAD still
1.25.1), shellcheck CVE-2021-28794 (Class 1).

**podman CVE-2026-57231 lapses 2026-08-06 (in two days)** and still has no lever —
verified today: `nixos-26.05` HEAD is still podman **5.8.2** and the backport
[nixpkgs#536367](https://github.com/NixOS/nixpkgs/pull/536367) is still a *draft*,
untouched since 2026-07-20. Renewed in the same pass to avoid an immediate re-red
(the #1240 pattern).

The three Jenkins-Git CPE-collision entries (CVE-2022-30947/-36882/-36883) are no
longer reported either, but they are Class-1 documented false positives on a yearly
re-check (exp 2027-06-23) and are retained as-is — dropping them buys nothing and
risks flapping if the NVD CPE data changes back.

## Scope

- Remove the five dead entries, each with the reason recorded in the register.
- Add a new time-boxed block for CVE-2026-66033 / -66034 / -66035 (expires
  **2026-08-31**) with provenance, reachability and the nixpkgs#547491 status.
- Renew podman CVE-2026-57231 to 2026-08-31 with a dated re-verification note.
- Changelog entry (root + `assets/workspace/.devcontainer` mirror).

Register-only — no image or code change, so it reaches `main` at the next promote.

## Out of scope (follow-ups)

- **Pin advance:** gawk **5.4.1** has now reached `nixos-26.05`, so the gawk block
  (4 CVEs, exp 08-18) finally has a rev-advance target — separate issue, since it
  rebuilds the image (the #1273 pattern).
- On a red gate the job aborts before "Build the Nix image for SBOM generation", so
  the CycloneDX SBOM and the Trivy defence-in-depth view are missing from the
  artifact exactly when they are most useful (compare artifact sizes: 17 kB on
  2026-08-03 vs 466 kB on 2026-07-30). Worth reordering or making the SBOM steps
  `if: always()`.
- The #1257 gap is now live-proven: `check-expirations` failing kills the scheduled
  run *before* the tracking-issue automation can fire.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 06:57 AM_

Fixed on `dev` by #1329 (merge `13417e40`).

- New libssh2 block (exp 2026-08-31) for CVE-2026-66033 / -66034 / -66035.
- Five dead entries pruned (CVE-2026-55200, -41992, -11979, -56123, -10846) — all already fixed at the pinned rev by the #1273 pin advance.
- podman CVE-2026-57231 renewed 2026-08-06 → 2026-08-31 (still no rev-advance lever).

PR CI fully green, including the in-CI **Security Scan** job — the vulnix gate passes on the same closure that has been red since 2026-07-31. Follow-up #1328 (pin advance to drop the gawk block) remains open.

