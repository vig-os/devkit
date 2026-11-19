---
type: issue
state: open
created: 2026-11-18T13:39:54Z
updated: 2026-11-18T13:39:54Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/2089
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-19T10:06:54.950Z
---

# [Issue 2089]: [Security exception register (main): exceptions expire 2026-11-25](https://github.com/vig-os/devkit/issues/2089)

The following security exceptions on `main` expire on **2026-11-25** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2025-15281` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-4046` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-4437` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5435` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5450` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-5928` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `main`
- **Expiry date:** 2026-11-25
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/44315872010

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-main` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
