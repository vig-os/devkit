---
type: issue
state: closed
created: 2026-07-23T08:34:04Z
updated: 2026-07-23T11:00:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1260
comments: 1
labels: chore, security
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-23T15:08:26.549Z
---

# [Issue 1260]: [curl 8.20.0 CVE exception batch expired 2026-07-22 — check-expirations now blocks all CI](https://github.com/vig-os/devkit/issues/1260)

## Description

The `.vulnixignore` exception block for the curl 8.20.0 advisory batch
(#941 triage, 2026-07-08: CVE-2026-10536, CVE-2026-11856, CVE-2026-8925,
CVE-2026-9079, CVE-2026-11564, CVE-2026-8924, CVE-2026-8926, CVE-2026-8927,
CVE-2026-8286, CVE-2026-11352, CVE-2026-11586, CVE-2026-12064, CVE-2026-8932,
CVE-2026-9545, CVE-2026-9546, CVE-2026-9547, CVE-2026-9080) carries
`Expiration: 2026-07-22`, which has now passed. `check-expirations` (pre-commit
+ CI) fails on every run, on `dev` and `release/1.4.1` alike (the file is
identical on both), so as of 2026-07-23 every PR CI run is red — including the
1.4.1 train's (first observed on the local hook suite for PR #1259).

Note the openssh CVE-2026-60002 entry expires 2026-07-24 (tomorrow) — worth
resolving in the same pass.

## Expected Behavior

Per the register's own protocol: check whether a fixed curl release has reached
the pinned nixpkgs channel (the entry was accepted awaiting-upstream because
8.20.0 was the newest release everywhere) — if yes, advance the rev and drop
the block; if not, re-verify the awaiting-upstream rationale and extend the
expiry (same model as the gawk extension, #1240).

## Impact

CI-blocking for every branch; blocks the 1.4.1 promote until resolved on the
release branch.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 11:00 AM_

Duplicate of #1257 — the nightly-scan session filed it this morning and PR #1258 (renewal of both blocks to 2026-08-15) merged into `release/1.4.1` at 09:48Z, before this issue was picked up. Closing as duplicate; the flip-to-rev-advance evidence is recorded on #1257.

