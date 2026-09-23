---
type: issue
state: closed
created: 2026-09-16T09:40:52Z
updated: 2026-09-18T08:03:20Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1634
comments: 2
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-19T07:15:13.840Z
---

# [Issue 1634]: [Security exception register (main): exceptions expire 2026-09-23](https://github.com/vig-os/devkit/issues/1634)

The following security exceptions on `main` expire on **2026-09-23** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

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

- **Scanned ref:** `main`
- **Expiry date:** 2026-09-23
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35080687787

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-main` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 16, 2026 at 05:49 PM_

Reconciled on `dev` by #1638 (merged as 3d1d127b). **Staying open**: the
reconciliation has not reached `main` yet.

**Same incident as #1635** — the registers on the two refs were byte-identical
when these issues were filed, so one re-verification covers both. All 16
entries in the 2026-09-23 block were checked against the 2026-09-16 scan
(`35080687787`, both lanes) and every one is still a live finding: the closure
still ships curl 8.21.0 and openssl 3.6.3 on `main` as well. Nothing was
deletable; the block moved 09-23 -> 10-21 because its remediation lever
(`NixOS/nixpkgs#563094`, still open) projects to land after the 2026-09-21
advance. Full rationale in #1635 and in the register.

**Why this cannot be closed yet.** `main` still carries the pre-#1638 register
and therefore still expires on 2026-09-23:

```
$ git show origin/main:.vulnixignore | grep '^Expiration:'
Expiration: 2027-06-23
Expiration: 2026-10-14
Expiration: 2026-09-30
Expiration: 2026-10-07
Expiration: 2026-09-23   <- still the old date
```

`main`'s register only moves via a release train: `update-nixpkgs.yml` targets
`dev` only, and `prepare-hotfix.yml` is not on `main` yet (#1623, unreleased).

**Consequence if no train ships before 2026-09-24:** `main`'s copy of the block
lapses and `check-expirations` fails on the `main` nightly lane. It does *not*
block a release train — under gitflow the release branch is cut from `dev` and
carries the reconciled register — but the `main` lane will be red until a train
lands, on top of the #1637 redness from the same day.

**Closes when** the next release train carries the register to `main`.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 18, 2026 at 08:03 AM_

Reconciled — closing.

The 2026-09-23 block no longer exists on either ref. `.vulnixignore` on `main` and `dev` is byte-identical and carries only these expiries:

- 2026-09-30, 2026-10-07, 2026-10-14, 2026-10-21, 2026-10-28, 2026-11-04, and the yearly 2027-06-23

How the cliff was cleared, per the register's own rule (entries die or are re-verified, never silently rolled forward):

- `7d1ac117` (2026-09-07) — the whole rsync block (8 entries, 2026-09-23) **deleted**, cleared by the pin advance 16 days before expiry.
- `3f220cc2` / `2bad1f0f` (2026-09-16) — the libxml2 2.15.4 batch excepted on its own date, and the curl + openssl block **re-dated** off the shared 09-23 cliff onto 10-21, each with the rationale re-stated.

`check-expirations` is consequently no longer in the failure path: the 2026-09-17 nightly (run 35207126776) went red on the CVE gate alone, with no expiry error on either ref.

Note for whoever picks up the next re-date: curl 8.22.0, openssl 3.6.4, libxml2 2.15.4 and pcre2 10.48 now all ride the one `staging-next-26.05` -> `release-26.05` hop. When it lands, those four blocks should be **deleted together**, not renewed.

