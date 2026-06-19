---
type: issue
state: closed
created: 2026-06-09T08:31:00Z
updated: 2026-06-18T09:12:00Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/567
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-19T07:20:06.972Z
---

# [Issue 567]: [Nightly security scan: HIGH/CRITICAL vulnerabilities in :latest](https://github.com/vig-os/devcontainer/issues/567)

Nightly scan found **fixable HIGH/CRITICAL** vulnerabilities in the resolved image below (after `.trivyignore`).

- **Image (resolved):** `ghcr.io/vig-os/devcontainer@sha256:75129ebc8d34a128b5a6c841277babf9d375a9a4ae3197ee9cf9ed4303c19e59`
- **Tag pulled:** `ghcr.io/vig-os/devcontainer:latest`
- **Scan date (UTC):** 2026-06-09T08:30:59Z
- **Workflow run:** https://github.com/vig-os/devcontainer/actions/runs/27193811318
- **Security tab:** https://github.com/vig-os/devcontainer/security

Close this issue after the image is remediated and the next scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 18, 2026 at 09:11 AM_

Remediated in v0.3.5 (2026-06-10). The nightly security scan gate has passed continuously since 2026-06-11; latest passing run: https://github.com/vig-os/devcontainer/actions/runs/27679283586 (2026-06-17). Closing per the issue's close condition (image remediated and next scheduled run passes the gate).

