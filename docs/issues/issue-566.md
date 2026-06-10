---
type: issue
state: closed
created: 2026-06-09T08:25:21Z
updated: 2026-06-09T21:28:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/566
comments: 0
labels: priority:low, area:image, effort:small, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:23.190Z
---

# [Issue 566]: [security(image): triage and accept Debian won't-fix low CVEs in .trivyignore](https://github.com/vig-os/devcontainer/issues/566)

## Bucket E - Accept Debian won't-fix low CVEs

The ~395 LOW Trivy findings are dominated by ancient Debian/upstream **won't-fix** CVEs that have no available patch.

### Examples
CVE-2010-4756, CVE-2011-4116, CVE-2011-3374, CVE-2007-5686, CVE-2013-4392, CVE-2019-1010022..25, CVE-2018-20796, CVE-2022-3219, CVE-2012-2663 - mostly glibc, tar, coreutils, ncurses, perl.

### Why low priority
- They never block CI: the nightly gate only fails on **fixable HIGH/CRITICAL** (`ignore-unfixed: true` in `.github/workflows/security-scan.yml`).
- No upstream fix exists, so the only lever is documentation/acceptance.

### Action
- [ ] Add expiry-dated entries to `.trivyignore` for the won't-fix lows, with a single shared risk note
- [ ] Keep the existing expiration-enforcement model (expired entries fail CI -> forced periodic review), consistent with the IEC 62304 exception register
- [ ] Confirm the Security tab LOW count drops to reflect accepted risk

### Note
Re-run after buckets B-D + a release land first - many of the current lows will disappear once `:latest` is refreshed, leaving a smaller, accurate set to accept.

Refs: #512, #521
