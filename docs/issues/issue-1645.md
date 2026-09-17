---
type: issue
state: open
created: 2026-09-17T09:55:50Z
updated: 2026-09-17T09:55:50Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1645
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T11:46:24.660Z
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
