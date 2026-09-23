---
type: issue
state: open
created: 2026-09-23T09:44:24Z
updated: 2026-09-23T12:59:51Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1667
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-23T14:38:46.741Z
---

# [Issue 1667]: [Security exception register (main): exceptions expire 2026-09-30](https://github.com/vig-os/devkit/issues/1667)

The following security exceptions on `main` expire on **2026-09-30** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-27820` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-11822` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-11824` — `.vulnixignore` (7 day(s) left)
- `CVE-2025-59777` — `.vulnixignore` (7 day(s) left)
- `CVE-2025-62689` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `main`
- **Expiry date:** 2026-09-30
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35844608653

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-main` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 12:59 PM_

**Still open — `main`'s register is not reconciled, and this one is time-critical.**

The fix landed on `dev` in #1670 (`b04a8ff5`) and closed #1666. `main` is untouched: its register still carries **32 entries** including `Expiration: 2026-09-30`, because the register travels to `main` only with a release train.

`check-expirations` runs in **all PR CI, in pre-commit, in both nightly lanes and in the release train**, so from **Thursday 2026-10-01** every lane on `main` goes red — not just the two scan lanes.

`dev` is 44 commits and 6 changelog entries ahead of `main` (last tag 1.15.1), so a **1.16.0 train before 2026-09-30** is what closes this; the hotfix lane is the fallback if it slips.

