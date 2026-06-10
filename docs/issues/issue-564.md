---
type: issue
state: closed
created: 2026-06-09T08:24:44Z
updated: 2026-06-09T21:28:11Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/564
comments: 0
labels: priority:high, area:image, effort:small, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:24.090Z
---

# [Issue 564]: [security(image): refresh bundled gh and uv to clear Go and Rust CVEs](https://github.com/vig-os/devcontainer/issues/564)

## Bucket C - Bundled tools (gh, uv/uvx)

HIGH/medium CVEs in the embedded Go stdlib (`gh`) and Rust crates (`uv`/`uvx`).

### gh (Go stdlib + gh)
CVE-2026-48501, CVE-2026-42504, CVE-2026-42499, CVE-2026-39820/39823/39825/39826/39836, CVE-2026-33811/33814 (and others) - all HIGH.

### uv / uvx (Rust crates)
- rustls-webpki GHSA-82j2-j2ch-gfr8 (HIGH)
- rkyv GHSA-vfvv-c25p-m7mm, astral-tokio-tar GHSA-fp55-jw48-c537 / GHSA-3cv2-h65g-fgmm, tar GHSA-3pv8-6f4r-ffg2, uv GHSA-4gg8-gxpx-9rph (medium/low)

### Why this is low-effort
`Containerfile` fetches the **latest** `gh` and `uv` at build time (not pinned - see the `GH_VERSION`/`UV_VERSION` `curl ... releases/latest` steps around lines 89 and 225). A fresh image build pulls fixed versions automatically once upstream ships them.

### Action
- [ ] Trigger an image rebuild (or release `dev`) so newest `gh`/`uv` are baked in
- [ ] For any CVE not yet fixed upstream, add an expiry-bounded entry to `.trivyignore` (model already used for CVE-2026-42504)
- [ ] Re-run nightly scan and confirm the `usr/local/bin/gh|uv|uvx` findings clear

### Context
`:latest` is release `0.3.4` (Apr 29); `dev` is ~70 commits ahead, so a release alone will refresh these tools.

Refs: #512, #521
