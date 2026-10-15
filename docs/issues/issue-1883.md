---
type: issue
state: open
created: 2026-10-14T09:55:36Z
updated: 2026-10-14T09:55:36Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1883
comments: 0
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:47.915Z
---

# [Issue 1883]: [Security exception register (dev): exceptions expire 2026-10-21](https://github.com/vig-os/devkit/issues/1883)

The following security exceptions on `dev` expire on **2026-10-21** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2025-59777` — `.vulnixignore` (7 day(s) left)
- `CVE-2025-62689` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-10-21
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/38545798347

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
