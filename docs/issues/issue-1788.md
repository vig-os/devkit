---
type: issue
state: closed
created: 2026-09-30T10:54:10Z
updated: 2026-10-05T09:38:37Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1788
comments: 2
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:51:02.114Z
---

# [Issue 1788]: [Security exception register (main): exceptions expire 2026-10-07](https://github.com/vig-os/devkit/issues/1788)

The following security exceptions on `main` expire on **2026-10-07** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-53432` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-53433` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `main`
- **Expiry date:** 2026-10-07
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/36705134920

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-main` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 30, 2026 at 08:16 PM_

The renewal landed on `dev` in #1791 (fzf block → 2026-11-18). `main` still expires on **2026-10-07**, so the next train must be promoted before then to reconcile this register. Close this when that train reaches `main`.

---

# [Comment #2]() by [c-vigo]()

_Posted on October 5, 2026 at 09:38 AM_

Reconciled on `main` by the 1.18.0 release (91083c03, promoted 2026-10-05). The fzf block (CVE-2026-53432/53433) was re-verified and renewed in #1789 (pin cf5e7650 and all three 26.05 branches still ship fzf 0.72.0, no backport). It is now dated 2026-11-18, so nothing on `main` expires 2026-10-07. The nightly security scan on `main` is green through 2026-10-04.

