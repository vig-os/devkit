---
type: issue
state: closed
created: 2026-06-09T08:25:05Z
updated: 2026-06-09T21:28:11Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/565
comments: 0
labels: priority:high, area:image, effort:medium, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:23.621Z
---

# [Issue 565]: [security(image): bump base image digest and apply OS security upgrades (perl/gnutls/zlib/curl/glibc)](https://github.com/vig-os/devcontainer/issues/565)

## Bucket D - Base OS package CVEs (Debian bookworm)

Vulnerabilities in OS packages from the base image.

### Verified: base digest is behind upstream (2026-06-09)
- Pinned in `Containerfile` line 4: `python:3.14-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb`
- Upstream latest `python:3.14-slim-bookworm`: `sha256:ec58d916f9e24a6035cab2bdf07f6206c4cc092a16613c60597534711332d9d6`
- A digest bump is still needed (not yet solved).

### Notable CVEs
- CRITICAL: perl CVE-2026-8376, perl-archive-tar CVE-2026-42496, gnutls CVE-2026-42010 / CVE-2026-33845, zlib CVE-2023-45853, CVE-2025-7458
- HIGH: curl (CVE-2026-6276 / CVE-2026-5773), rsync (CVE-2026-43618 / CVE-2026-29518), libssh2 CVE-2026-7598, libexpat CVE-2026-45186, krb5, glibc

### Action
- [ ] Bump the pinned base digest (`Containerfile` line 4) to the newest `python:3.14-slim-bookworm` (let Renovate `dockerfile` open the PR)
- [ ] Add a controlled `apt-get update && apt-get upgrade` security layer during build to pull Debian point-release fixes ahead of a new base tag
- [ ] Re-scan; only fixable HIGH/CRITICAL gate CI (nightly uses `ignore-unfixed: true`)

### Context
`:latest` is release `0.3.4` (Apr 29) and `dev` is ~70 commits ahead (incl. python 3.14.5 bump #539 and prior remediations #514). A **release of `dev` to `main`/`:latest`** will by itself clear a large share of the OS-package alerts currently shown against `image-latest.tar`. Prioritize cutting a release, then layer the digest bump + apt upgrade.

Refs: #512, #521
