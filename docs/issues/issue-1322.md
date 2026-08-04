---
type: issue
state: closed
created: 2026-07-31T07:49:47Z
updated: 2026-08-04T06:57:25Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1322
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:57.296Z
---

# [Issue 1322]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1322)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-07-31T07:49:47Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/30614074169
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 06:57 AM_

Fixed on `dev` by #1329 (merge `13417e40`), tracked in #1327.

The three blocking findings (libssh2 1.11.1 — CVE-2026-66033 / -66034 / -66035, 7.5 each) are now covered by a time-boxed exception expiring 2026-08-31: all are client-side flaws requiring a connection to a malicious SSH server, libssh2 enters the closure only as curl's scp/sftp backend, and no rev-advance exists (NixOS/nixpkgs#547491 is still on `staging`).

Verified by replaying `vulnix-gate` against this run's own `nix-image-cve-scan-dev` artifact (exit 0), and by the green in-CI Security Scan job on the PR. The next scheduled run on `dev` should pass.

