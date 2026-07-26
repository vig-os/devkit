---
type: issue
state: open
created: 2026-07-25T07:14:44Z
updated: 2026-07-25T07:14:44Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1264
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-26T05:38:57.093Z
---

# [Issue 1264]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1264)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-07-25T07:14:43Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/30148910775
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
