---
type: issue
state: open
created: 2026-11-06T01:15:46Z
updated: 2026-11-17T19:35:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2052
comments: 2
labels: area:image, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:46.872Z
---

# [Issue 2052]: [vulnix: new HIGH sqlite 3.53.3 and rsync 3.5.0 CVEs block the release gate (no nixpkgs fix yet)](https://github.com/vig-os/devkit/issues/2052)

The `release.yml` Vulnix CVE Gate failed for 1.19.0-rc4 (run 42140837792) on five findings published 2026-10-30 and 2026-11-03:

| CVE | Package | CVSS | Summary |
|---|---|---|---|
| CVE-2026-119373 | sqlite 3.53.3 | 7.8 AV:L/UI:R | FTS5 heap overflow, `fts5MergeRowidLists` |
| CVE-2026-119374 | sqlite 3.53.3 | 7.8 AV:L/UI:R | FTS5 heap overflow, `fts5DoSecureDelete`; needs a crafted DB file |
| CVE-2026-119379 | sqlite 3.53.3 | 7.8 AV:L/UI:R | session extension, `sqlite3changeset_apply` |
| CVE-2026-119586 | sqlite 3.53.3 | 7.8 AV:L/UI:R | CLI `.recover` dot-command injection |
| CVE-2026-119741 | rsync 3.5.0 | 7.5 AV:N | DoS in a public rsync daemon's delta-transfer sender |

Fixed upstream in sqlite 3.54.0/3.54.2 and rsync 3.5.2. **Not yet in nixpkgs**: the pinned rev, `nixos-26.05` and `nixpkgs-unstable` all carry sqlite 3.53.3 and rsync 3.5.0, with no CVE patches (checked 2026-11-06). The pin advance cannot fix this yet.

**Plan:** time-boxed exact-scope `awaiting-upstream` exceptions in `.vulnixignore`, expiring 2026-11-18 (Wednesday grid), each with a risk note. Then remove them through the weekly nixpkgs advance once the fixed versions land.
---

# [Comment #1]() by [gerchowl]()

_Posted on November 6, 2026 at 01:54 AM_

Exceptions landed in release/1.19.0 via #2053 (expire 2026-11-18). Follow-up note from review: NVD lists CVE-2026-119586 and CVE-2026-119741 without an upper version bound (versionEndExcluding null), although the descriptions say 'through 3.54.1' / 'before 3.5.2'. vulnix may therefore still flag sqlite 3.54.2 and rsync 3.5.2 after the pin advance, until NVD corrects the data. Expect a version-mismatch triage then, not a clean delete.

---

# [Comment #2]() by [gerchowl]()

_Posted on November 17, 2026 at 07:35 PM_

Reconciled on 2026-11-17, the day before the 2026-11-18 expiry, in #2081 (into `dev`). Nothing is fixed at the pin, so nothing is deleted. Each entry was re-verified and re-dated by its lever:

| Entry | Status, 2026-11-17 | New expiry |
|---|---|---|
| rsync CVE-2026-119741 | Fixed on `nixos-26.05` head `b349185b`: nixpkgs `190957f1` (rsync 3.5.0 -> 3.5.2, NixOS/nixpkgs#584501, carried by staging-next iteration 10, NixOS/nixpkgs#584522). The pin `08d3a975` and #1821's `f1e5c356` both predate it. **Exit: the next pin advance to a rev at or after `190957f1`; delete it then.** | 2026-12-02 |
| sqlite CVE-2026-119373 / -119374 / -119379 | Fixed in upstream 3.54.0 only; the fix commits are not in `version-3.53.4`. In nixpkgs, 3.54.0 is staging/unstable only (NixOS/nixpkgs#572495). Every 26.05 branch ships 3.53.3, and no backport PR is open. | 2026-12-09 |
| sqlite CVE-2026-119586 | **Correction:** sqlite 3.54.2 does not exist (the latest release is 3.54.1), and upstream rejects the CVE as "not a bug in the core SQLite library", with `--safe` as the mitigation. No version fixes it. It is now classed not-exploitable, and its exact `@3.53.3` key re-gates it at the sqlite bump. | 2026-12-09 |
| fzf CVE-2026-53432 / -53433 | Still 0.72.0 on every 26.05 branch. The only backport, NixOS/nixpkgs#572684, was closed unmerged; none is open. | 2026-12-16 |

On the review note above: NVD now gives every range an upper bound (`sqlite` < 3.54.0, or <= 3.54.1 for 119586; `rsync` <= 3.5.1). rsync 3.5.2 should therefore drop out cleanly; it should not need a version-mismatch triage. 119586 will need re-keying when sqlite moves to 3.54.x.

Verification:
- All seven are still live in the dev lane of nightly run 44099322680, and NVD shows no new HIGH CVE for these packages.
- With today set to 2026-11-19, `check-expirations` and `vulnix-gate` against that artifact both exited 1 before the change and both exit 0 after it.

Keep this issue open until the pin advance past `b349185b` deletes the rsync entry and a 26.05 sqlite >= 3.54.0 deletes the three FTS5/session entries. The dev-lane notice #2072 is resolved by #2081. The main-lane notice #2073 is resolved when the register reaches `main` through the release-neutral lane.


