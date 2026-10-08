---
type: issue
state: open
created: 2026-10-07T11:31:30Z
updated: 2026-10-07T11:31:30Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1847
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-08T08:45:27.482Z
---

# [Issue 1847]: [Security exception register (dev): exceptions expire 2026-10-14](https://github.com/vig-os/devkit/issues/1847)

The following security exceptions on `dev` expire on **2026-10-14** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2025-15281` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-4046` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-4437` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5435` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5450` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5928` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-10-14
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/37614551910

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
