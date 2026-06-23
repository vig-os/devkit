---
type: issue
state: open
created: 2026-04-14T06:53:24Z
updated: 2026-06-23T06:56:35Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/521
comments: 2
labels: security, security-scan
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:54.972Z
---

# [Issue 521]: [Nightly security scan: HIGH/CRITICAL vulnerabilities in :latest](https://github.com/vig-os/devcontainer/issues/521)

Nightly scan found **fixable HIGH/CRITICAL** vulnerabilities in the resolved image below (after `.trivyignore`).

- **Image (resolved):** `ghcr.io/vig-os/devcontainer@sha256:e3fed6eadb3a1daeae4c7c455ccf52e1152d35e6292b044fb50c6c731cc104d2`
- **Tag pulled:** `ghcr.io/vig-os/devcontainer:latest`
- **Scan date (UTC):** 2026-04-14T06:53:24Z
- **Workflow run:** https://github.com/vig-os/devcontainer/actions/runs/24385257286
- **Security tab:** https://github.com/vig-os/devcontainer/security

Close this issue after the image is remediated and the next scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on April 29, 2026 at 07:37 AM_

## Triage: no code change needed (resolves with next release)

The only fixable HIGH after `.trivyignore` is **CVE-2026-32280** (Go stdlib `crypto/x509` chain-building DoS, v1.26.1), present in the bundled `gh` CLI in two binaries.

**Why we are not patching `:latest` directly or adding to `.trivyignore`:**

- Upstream [gh 2.92.0](https://github.com/cli/cli/releases/tag/v2.92.0) (released 2026-04-28) bumped Go to **1.26.2**, which carries the fix for CVE-2026-32280 *and* the three already-suppressed sibling CVEs (`-32281`, `-32288`, `-32289`).
- `dev` already encodes this expectation in `tests/test_image.py:22` (`"gh": "2.92."`), so the next image build will install the patched binary.
- `:latest` rebuilds only on a final release promote (`release.yml` → `promote-release.yml`); the failed scan ran against release **0.3.3** (built 2026-04-10, before gh 2.92.0 existed).
- Adding a `.trivyignore` entry now and removing it in the next release PR would be churn for zero added safety — the gate will naturally pass once `0.3.4` is promoted to `:latest`.

**Cleanup at next release (`0.3.4`):**

- Verify `gh --version` ≥ 2.92.0 in the released image (already covered by image tests).
- Remove all four `CVE-2026-3228x` blocks from `.trivyignore`.

**Closing this issue:** leave open; closes naturally after the post-0.3.4 nightly scan is green.

---

# [Comment #2]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

The apt-CVE surface this gate tracks changes under the Nix image: Trivy-on-apt is replaced by vulnix + SBOM in #637, and the Debian path is decommissioned in #642 (both part of #625). This gate will be re-pointed/closed once the new scan passes its gate (with #642).

