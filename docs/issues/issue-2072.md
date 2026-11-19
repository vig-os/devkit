---
type: issue
state: closed
created: 2026-11-11T12:25:42Z
updated: 2026-11-18T10:27:07Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/2072
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-19T10:06:57.746Z
---

# [Issue 2072]: [Security exception register (dev): exceptions expire 2026-11-18](https://github.com/vig-os/devkit/issues/2072)

The following security exceptions on `dev` expire on **2026-11-18** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-53432` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-53433` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-119373@sqlite@3.53.3` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-119374@sqlite@3.53.3` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-119379@sqlite@3.53.3` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-119586@sqlite@3.53.3` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-119741@rsync@3.5.0` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-11-18
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/43020107320

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [gerchowl]()

_Posted on November 18, 2026 at 10:27 AM_

Resolved on dev by #2081: the 7 entries are re-triaged and the next expiries are 2026-12-02, 12-09 and 12-16. Main got the fix in 1.19.1, and #2073 is closed.

