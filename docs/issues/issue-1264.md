---
type: issue
state: closed
created: 2026-07-25T07:14:44Z
updated: 2026-07-26T12:51:19Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1264
comments: 1
labels: security, security-scan
assignees: none
milestone: 1.4.2
projects: none
parent: none
children: none
synced: 2026-07-26T14:51:12.305Z
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
---

# [Comment #1]() by [c-vigo]()

_Posted on July 26, 2026 at 12:51 PM_

Remediated in PR #1274 (merged to dev @ba5093ca): time-boxed `.vulnixignore` exception block for the five unbound 1.25.1 HIGH/CRITICAL CVEs (CVE-2026-50252, -32665, -40691, -44690, -55973; expires 2026-08-31), verified online against NLnet Labs advisories and nixpkgs branch state — all fixed upstream in unbound 1.25.2 (2026-07-22), nixpkgs bump in staging-26.05 only (NixOS/nixpkgs#544542/#544610), so no rev-advance available yet (re-check tracked in #1273). Closure provenance: libunbound via podman → systemd → gnutls only; no unbound daemon runs in the image.

**Gate live-proven on dev**: dispatched security-scan run https://github.com/vig-os/devkit/actions/runs/30194392375 — `Scan Nix image (vulnix + SBOM) [dev]` **success**.

Shipping in 1.4.2 (rc1 in flight).

