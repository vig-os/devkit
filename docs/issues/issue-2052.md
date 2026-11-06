---
type: issue
state: open
created: 2026-11-06T01:15:46Z
updated: 2026-11-06T01:54:32Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2052
comments: 1
labels: area:image, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T09:11:25.976Z
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

