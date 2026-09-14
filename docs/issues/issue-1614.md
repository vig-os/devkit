---
type: issue
state: open
created: 2026-09-12T09:05:12Z
updated: 2026-09-14T07:07:01Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1614
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-14T07:48:38.828Z
---

# [Issue 1614]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1614)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-12T09:05:11Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/34684718095
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 07:07 AM_

Same incident as #1615; diagnosis and fix in #1619 (register block expiring **2026-09-23**, per-CVE triage in the block and the PR body).

This issue stays open, deliberately: as with the rsync batch (#1592), #1619 excepts the batch on `dev` only and the register reaches `main` with the next release train. The nightly `main` lane will keep re-filing under this title (dedup) until then — intended behaviour, not a new finding.

Ordering note for whoever runs that train: the block expires **2026-09-23**. If the weekly pin advance (next: 2026-09-21) has shipped curl 8.22.0 / openssl 3.6.4 by then — both are already merged to `staging-26.05` and riding [NixOS/nixpkgs#563094](https://github.com/NixOS/nixpkgs/pull/563094) — drop the block instead of carrying it to `main`.

