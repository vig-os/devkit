---
type: issue
state: closed
created: 2026-08-08T05:44:56Z
updated: 2026-08-10T11:17:19Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1393
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:29.311Z
---

# [Issue 1393]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1393)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-08-08T05:44:55Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/31242210380
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 11:17 AM_

**Resolved — closing.**

**Root cause:** a single blocking finding, `CVE-2026-66032` (CVSS 8.8) in `libssh2 1.11.1`:

```
1 unexcepted HIGH/CRITICAL or unscored vulnix finding(s) (CVSS >= 7.0 or no score):
  - CVE-2026-66032 (CVSS 8.8) in libssh2 1.11.1
```

Not a new vulnerability — an exception-propagation lag. The register entry for it
landed in `964c7d48` (#1387) on `release/1.7.0` on 2026-08-07. That commit reached
`main` when the 1.7.0 release PR #1385 merged (2026-08-08 08:49Z), but had no path
to `dev` until the sync-main-to-dev PR #1395 merged (2026-08-10 10:01Z) — that PR
sat blocked on conflicts in the generated `docs/issues/` + `docs/pull-requests/`
mirror for two days. Every nightly in the gap re-reported the same CVE. The gate
logs corroborate the delta: the dev leg validated **27** exceptions where `main`
had **28**.

The HIGH/CRITICAL finding set was otherwise byte-identical between the two refs
(25 CVEs, all covered by the register).

**No code change required.** The `Expiration: 2026-09-02` libssh2 block stands as
written and drops whole on the nixpkgs rev-advance, once the staging-26.05
backport (NixOS/nixpkgs#550166) reaches the pinned nixos-26.05 channel.

**Verified green** by manual dispatch
https://github.com/vig-os/devkit/actions/runs/31382435161 — both legs:

```
Validated 28 exception(s) across 1 file(s)
No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 28 exception(s) applied
```

**Systemic note:** a security exception added on a release branch reaches `main` at
the release merge but `dev` only at the sync PR, so a conflicted sync leaves the
dev lane red and files a fresh tracking issue every night for the whole gap. Worth
a separate issue if we want that closed (cherry-pick register changes to `dev`
during the train, or suppress dev-leg issue creation when the delta is fully
explained by an unmerged sync).

