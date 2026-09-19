---
type: issue
state: closed
created: 2026-09-17T09:55:50Z
updated: 2026-09-18T09:29:41Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1645
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-19T07:15:12.685Z
---

# [Issue 1645]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1645)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-17T09:55:48Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35207126776
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 18, 2026 at 09:29 AM_

The next scheduled run passes the gate on `dev` — closing per this issue's own criterion.

- **Run:** https://github.com/vig-os/devkit/actions/runs/35329193958 (schedule, 2026-09-18T09:22:29Z), conclusion `success`
- **Job:** `Scan Nix image (vulnix + SBOM) [dev]` — `success`
- **Gate:** `No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 32 exception(s) applied`
- **Expiries:** `Validated 32 exception(s) across 1 file(s)` — nothing expired

Both CVEs that failed the 2026-09-17 run (35207126776) are now covered by the register, each with its own triage block and rationale rather than a blanket date:

- `CVE-2026-86140` (libxml2 2.15.3, 8.0) — `3f220cc2`, Expiration 2026-10-28
- `CVE-2026-89161` (pcre2 10.46 + 10.47, 7.4) — `e917b3e3`, Expiration 2026-11-04

That second commit landed *after* the 09-17 scan started, which is why that run was still red.

These are accepted-and-time-boxed, not fixed: the fix is a single `staging-next-26.05` -> `release-26.05` hop carrying curl 8.22.0, openssl 3.6.4, libxml2 2.15.4 and pcre2 10.48. When it lands, all four blocks get **deleted together**, not renewed — see #1634 and `docs/CONTAINER_SECURITY.md`.

