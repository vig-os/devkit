---
type: issue
state: closed
created: 2026-09-16T09:40:52Z
updated: 2026-09-16T17:48:39Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1635
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T07:29:37.906Z
---

# [Issue 1635]: [Security exception register (dev): exceptions expire 2026-09-23](https://github.com/vig-os/devkit/issues/1635)

The following security exceptions on `dev` expire on **2026-09-23** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-19931` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-18924` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-82209` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-80229` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-80230` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-80231` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-80255` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-82208` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-13608` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-63073` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-75803` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-14457` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-54874` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-63072` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-63075` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-63076` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-09-23
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35080687787

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 16, 2026 at 05:48 PM_

Reconciled on `dev` by #1638 (merged as 3d1d127b).

**This was a re-verification, not a date bump.** All 16 entries in the
2026-09-23 block were checked against the 2026-09-16 scan (`35080687787`, both
lanes): every one is still a live finding, because the closure still ships
curl 8.21.0 and openssl 3.6.3. Nothing was dead weight, so nothing was
deletable — no entry was dropped.

**Why it was re-dated to 2026-10-21 instead of left to die on remediation.**
The block's own 09-14 note bet on the 2026-09-21 weekly advance, which assumed
`staging-next-26.05` iteration 7 reaching `release-26.05` first. It has not:
`NixOS/nixpkgs#563094` opened 2026-09-14 and is still open, and the iteration
cadence (iteration 5 merged 08-18, iteration 6 merged 09-05) projects the next
merge to roughly 09-23 — *after* Monday's advance, with the `nixos-26.05`
channel trailing `release-26.05` by about a day on top of that.

Holding 09-23 would therefore most likely have lapsed the block on 09-24, and
`check-expirations` runs in `ci.yml` as well as the two nightly lanes, so a
lapse takes **every open PR** red, not just the scan lanes — the #1547 failure
mode. 10-21 clears the projected landing by four weeks and two further weekly
advances while keeping the block on its own Wednesday.

The assessment itself is untouched: no risk judgement was re-opened or changed,
and the exit condition stands — the block dies on the advance that ships curl
8.22.0 and openssl 3.6.4.

**Grid after this pass** (one block per Wednesday, all six verified to land on a
Wednesday):

```
09-30  lower-reachability             (5)
10-07  fzf                            (2)
10-14  glibc                          (6)
10-21  curl 8.21.0 + openssl 3.6.3   (16)   <- moved
10-28  libxml2 CVE-2026-86140         (1)   <- new (#1636)
2027-06-23  Class-1 shellcheck        (1)
```

`check-expirations` validates 31 exceptions on the merged `dev` register.

All three of curl, openssl and libxml2 now share one remediation lever
(`NixOS/nixpkgs#563094`) and should be **deleted together** on the advance that
ships the fixed versions — the dates above are a backstop, not a plan.

`main` (#1634) stays open: its register only moves via a release train.

