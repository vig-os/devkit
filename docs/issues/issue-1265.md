---
type: issue
state: closed
created: 2026-07-25T07:14:49Z
updated: 2026-07-26T15:28:27Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1265
comments: 2
labels: security, security-scan
assignees: none
milestone: 1.4.2
projects: none
parent: none
children: none
synced: 2026-07-27T05:57:39.539Z
---

# [Issue 1265]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1265)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-07-25T07:14:48Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/30148910775
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 26, 2026 at 12:51 PM_

Same root cause and remediation as #1264 (dev and main share the nixpkgs pin, identical closures): fixed by PR #1274 on dev — see the diagnosis and exception rationale there. The dev scan leg is already green (run https://github.com/vig-os/devkit/actions/runs/30194392375); the main leg goes green when the fix reaches `main` at the **1.4.2 promotion** (train in flight, rc1 building).

If a nightly run still fails the main leg after 1.4.2 promotes, the workflow will open a fresh tracking issue — signal is not lost by closing this one now.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 26, 2026 at 03:28 PM_

1.4.2 promoted 2026-07-26 15:20Z. Post-promote security-scan run https://github.com/vig-os/devkit/actions/runs/30208092212: **both legs green** (main + dev) — gate remediation live-proven on main as promised at close.

