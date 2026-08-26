---
type: issue
state: open
created: 2026-08-26T05:32:28Z
updated: 2026-08-26T11:45:25Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1564
comments: 0
labels: security, security-scan
assignees: none
milestone: 1.11.1
projects: none
parent: none
children: none
synced: 2026-08-26T13:51:56.341Z
---

# [Issue 1564]: [Security exception register (main): exceptions expire 2026-09-02](https://github.com/vig-os/devkit/issues/1564)

The following security exceptions on `main` expire on **2026-09-02** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-57231` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `main`
- **Expiry date:** 2026-09-02
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/32934376451

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-main` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
