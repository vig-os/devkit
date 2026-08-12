---
type: issue
state: closed
created: 2026-08-08T05:45:12Z
updated: 2026-08-10T11:17:21Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1394
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:28.753Z
---

# [Issue 1394]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1394)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-08-08T05:45:11Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/31242210380
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 11:17 AM_

**Resolved — closing.** Self-resolved on the 2026-08-09 nightly; confirmed today.

**Root cause:** a single blocking finding, `CVE-2026-66032` (CVSS 8.8) in
`libssh2 1.11.1` — same CVE as the dev-leg issue #1393, but a different mechanism
on this ref: a scheduling race, not a propagation lag.

The exception for it landed in `964c7d48` (#1387) and reached `main` when the 1.7.0
release PR #1385 merged at **2026-08-08 08:49Z**. This scan ran at **05:45Z the
same morning** — the nightly beat the exception onto `main` by about three hours.
The 08-09 and 08-10 nightlies both passed on `main` unaided.

**No code change required.** The `Expiration: 2026-09-02` libssh2 block stands as
written and drops whole on the nixpkgs rev-advance, once the staging-26.05 backport
(NixOS/nixpkgs#550166) reaches the pinned nixos-26.05 channel.

**Verified green** by manual dispatch
https://github.com/vig-os/devkit/actions/runs/31382435161 — both legs:

```
Validated 28 exception(s) across 1 file(s)
No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 28 exception(s) applied
```

