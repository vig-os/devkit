---
type: issue
state: closed
created: 2026-09-30T10:54:14Z
updated: 2026-09-30T20:16:23Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1789
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-01T08:40:51.859Z
---

# [Issue 1789]: [Security exception register (dev): exceptions expire 2026-10-07](https://github.com/vig-os/devkit/issues/1789)

The following security exceptions on `dev` expire on **2026-10-07** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-53432` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-53433` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-10-07
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/36705134920

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 30, 2026 at 08:16 PM_

Reconciled on `dev` by #1791 (af8edbdf): the fzf CVE-2026-53432/53433 block was re-verified and renewed to 2026-11-18. The pin and all three 26.05 branches still ship fzf 0.72.0 and no backport is open, so there was no pin advance to remove the entries instead. `main`'s copy is tracked in #1788 and rides the next train.

