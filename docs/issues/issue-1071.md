---
type: issue
state: open
created: 2026-07-14T16:37:32Z
updated: 2026-07-14T16:37:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1071
comments: 0
labels: priority:blocking, security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:23.435Z
---

# [Issue 1071]: [gawk 5.4.0 CVE batch (CVE-2026-40467/-40468/-40469/-40553) fails vulnix gate, blocks 1.2.0-rc1](https://github.com/vig-os/devkit/issues/1071)

## Problem

The 1.2.0-rc1 candidate release ([run 29346662524](https://github.com/vig-os/devkit/actions/runs/29346662524)) failed at the blocking **Vulnix CVE Gate** on four fresh gawk 5.4.0 findings (published 2026-07-13 by CERT-PL, [advisory](https://cert.pl/en/posts/2026/07/CVE-2026-40467/)):

- **CVE-2026-40468** (CVSS 9.1) — integer overflow in `builtin.c`; memory exhaustion / heap corruption with attacker-controlled bytes
- **CVE-2026-40469** (CVSS 9.1) — integer overflow in `builtin.c` `do_sub()`; heap corruption → crash; **32-bit builds only** per the advisory
- **CVE-2026-40467** (CVSS 7.5) — use-after-free in `io.c` `do_getline_redir()`; crash
- **CVE-2026-40553** (CVSS 7.5) — stack buffer overflow in `extension/readdir.c` `ftype()`; crash, unconfirmed code execution; requires the opt-in `readdir` extension (`-l readdir`)

## Remediation status (verified online 2026-07-14)

All four are fixed upstream in **gawk 5.4.1**. In nixpkgs the bump ([NixOS/nixpkgs#540158](https://github.com/NixOS/nixpkgs/pull/540158)) merged to `staging` on 2026-07-12 (gawk is a stdenv mass-rebuild) and has **not** reached any release branch — `nixos-26.05`, `release-26.05`, `staging-26.05`, `master`, and `nixpkgs-unstable` all still ship 5.4.0. The "advance the rev" lever has nowhere to land today.

## Fix

Per the exception-register model (`docs/CONTAINER_SECURITY.md`, precedents #941/#963): add a short-dated, per-CVE-annotated `.vulnixignore` block via PR **against `release/1.2.0`**, drop it and advance the pin once 5.4.1 lands in `nixos-26.05`. gawk is a stdenv closure member processing developer/CI-chosen awk programs and inputs only — single-user dev-container exposure, no untrusted input path.
