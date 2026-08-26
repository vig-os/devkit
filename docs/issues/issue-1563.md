---
type: issue
state: closed
created: 2026-08-26T05:32:28Z
updated: 2026-08-26T13:06:07Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1563
comments: 1
labels: security, security-scan
assignees: none
milestone: 1.11.1
projects: none
parent: none
children: none
synced: 2026-08-26T13:51:56.776Z
---

# [Issue 1563]: [Security exception register (dev): exceptions expire 2026-09-02](https://github.com/vig-os/devkit/issues/1563)

The following security exceptions on `dev` expire on **2026-09-02** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-57231` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-09-02
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/32934376451

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 26, 2026 at 01:06 PM_

Register reconciled by #1569 (merged to dev) against the f4f69867 pin advance (#1568) and the first scan on the new closure (run 32934376451's successor, dispatch run 32969211536): 14 entries deleted with tombstones, none renewed; vulnix-gate green with the surviving 14. Verification scan on merged dev: run 32972165168. The main-side twin #1564 closes when the 1.11.1 release merge lands this state on main.

