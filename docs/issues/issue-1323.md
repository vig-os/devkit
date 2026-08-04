---
type: issue
state: closed
created: 2026-07-31T07:50:03Z
updated: 2026-08-04T06:57:27Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1323
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:56.764Z
---

# [Issue 1323]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1323)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-07-31T07:50:02Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/30614074169
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 06:57 AM_

Fixed on `dev` by #1329 (merge `13417e40`), tracked in #1327. Same closure and same three libssh2 findings as #1322 — `dev` and `main` share the nixpkgs pin, so one register fix covers both.

Verified by replaying `vulnix-gate` against this run's own `nix-image-cve-scan-main` artifact (exit 0). Note that `main` only picks the fix up at the next **promote**, so the nightly `main` leg stays red until then.

