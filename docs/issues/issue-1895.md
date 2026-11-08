---
type: issue
state: open
created: 2026-10-15T09:36:57Z
updated: 2026-10-15T09:36:57Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1895
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-16T06:58:52.052Z
---

# [Issue 1895]: [Nightly security scan (dev): run failed before the vulnix gate](https://github.com/vig-os/devkit/issues/1895)

The nightly security scan for `dev` failed **before the vulnix gate ran**, so this run produced no CVE verdict at all — the closure is unscanned, not clean.

- **Scanned ref:** `dev`
- **Failing step:** Validate .vulnixignore exception expirations
- **Scan date (UTC):** 2026-10-15T09:36:55Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/38714126021

**Most likely cause:** an expired `.vulnixignore` exception. The register's expiry dates are *designed* to fire (Wednesday grid, see `docs/CONTAINER_SECURITY.md`); renew or drop the block and the scan resumes. Otherwise triage the failing step in the run log — a closure build or vulnix crash needs a different fix. Close this issue once a later scheduled run completes.
