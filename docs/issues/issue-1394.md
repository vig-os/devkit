---
type: issue
state: open
created: 2026-08-08T05:45:12Z
updated: 2026-08-08T05:45:12Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1394
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-09T03:48:34.829Z
---

# [Issue 1394]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1394)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-08-08T05:45:11Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/31242210380
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
