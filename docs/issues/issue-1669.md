---
type: issue
state: open
created: 2026-09-23T09:48:19Z
updated: 2026-09-23T13:00:01Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1669
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-23T14:38:45.717Z
---

# [Issue 1669]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1669)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-23T09:48:18Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35844608653
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 01:00 PM_

**Still open — `main` has neither the exception nor the closure change.**

The unbound exception landed on `dev` in #1670 (`b04a8ff5`); see #1668 for the triage, the re-verified provenance and the upstream lever status. `main`'s register carries no `CVE-2026-81642` entry and `main`'s closure still ships unbound 1.26.0, so its nightly lane stays red until a release train carries the register over.

Unlike #1668, this one cannot be cleared by the next scheduled run alone — it is gated on the same 1.16.0 train as #1667.

