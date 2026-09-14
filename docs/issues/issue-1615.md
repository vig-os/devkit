---
type: issue
state: open
created: 2026-09-12T09:05:31Z
updated: 2026-09-14T07:06:58Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1615
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-14T07:48:38.554Z
---

# [Issue 1615]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1615)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-12T09:05:29Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/34684718095
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 07:06 AM_

Same incident as #1614 — `main` and `dev` sit on the same pinned nixpkgs rev (`c25784012c`) and the two lanes' findings artifacts are byte-identical: the NVD feed picked up the curl 8.21.0 (9 CVEs) and openssl 3.6.3 (7 blocking CVEs) fix-release advisory batches in the 09-11 → 09-12 window. A feed event, not a closure change — the 2026-09-11 nightly ([34583730623](https://github.com/vig-os/devkit/actions/runs/34583730623)) was green on the same pin.

Fix: #1619 (full diagnosis, propagation table and per-CVE triage there and in the register block). All 16 are fixed in curl 8.22.0 / openssl 3.6.4, both riding the open [NixOS/nixpkgs#563094](https://github.com/NixOS/nixpkgs/pull/563094) toward `release-26.05`, so the pin-advance lever has nowhere to land today; a time-boxed exception block expiring **2026-09-23** covers the gap. This closes on the first green `dev` nightly after #1619 merges.

