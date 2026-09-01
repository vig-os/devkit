---
type: issue
state: open
created: 2026-09-01T09:48:27Z
updated: 2026-09-01T14:11:43Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1592
comments: 2
labels: security, security-scan
assignees: none
milestone: 1.13.0
projects: none
parent: none
children: none
synced: 2026-09-01T15:12:53.044Z
---

# [Issue 1592]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1592)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-01T09:48:25Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/33493764209
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 1, 2026 at 12:14 PM_

## Diagnosis

This issue and #1593 are the **same incident**, not two: both were opened by the same nightly run ([33493764209](https://github.com/vig-os/devkit/actions/runs/33493764209)), and both lanes fail on one package.

### Root cause

`rsync-3.4.4` — a direct member of the image env (`flake.nix:1118`). Overnight the NVD feed published **17 new rsync CVEs**; **8 are >= CVSS 7.0 and unexcepted**, identically on both refs:

| CVSS | CVE | Vector |
|---|---|---|
| 9.1 | CVE-2026-53791 | **daemon**: PROXY-header source-IP spoofing bypasses `hosts allow/deny` |
| 8.2 | CVE-2026-70461 | **daemon**: heap 1-byte OOB write via crafted `--files-from` entry |
| 8.1 | CVE-2026-70463 | **daemon**: `auth users` comma-only tokenizer drops `@Group Name` deny rules |
| 8.1 | CVE-2026-53795 | arbitrary file write via absolute `--temp-dir`/`--link-dest` |
| 7.8 | CVE-2026-53803 | symlink-follow on `--log-file`/`--write-batch`; LPE **where rsync is setuid or a privileged daemon** |
| 7.5 | CVE-2026-70455 | receiver DoS: `--zt=N` short alias evades `refuse options` |
| 7.1 | CVE-2026-53802 | **daemon**: arbitrary file read via symlinked `--files-from`/`--password-file` |
| 7.1 | CVE-2026-53784 | **daemon**: module-root path traversal when `use chroot` is off |

The remaining 9 of the 17 are below the gate's 7.0 threshold and need no exception.

### This is a feed event, not a closure change

The previous night's scan ([33386509290](https://github.com/vig-os/devkit/actions/runs/33386509290), 2026-08-31) was **green on the same pin**. Diffing the two findings sets: 17 new CVEs, all rsync, **zero gone, zero other packages changed**. No `.vulnixignore` entry expired either — the next expiry on the staggered grid is 2026-09-30.

The dev/main findings-count difference (54 vs 44) is unrelated and benign: dev's pin `c5c4a43b` is one weekly advance ahead of main's `f4f69867`, so dev's transitional closure carries two glibc generations (`-67` and `-84`). Those 10 extra findings are already excepted or sub-threshold.

### Remediation lever: exists, but has nowhere to land today

All 17 are fixed in **rsync 3.5.0**. Propagation state as of 2026-09-01:

| Branch | rsync |
|---|---|
| `staging-26.05` | **3.5.0** (merged 2026-08-28) |
| `staging-next-26.05` | **3.5.0** (backport [NixOS/nixpkgs#557467](https://github.com/NixOS/nixpkgs/pull/557467), merged 2026-08-29) |
| `release-26.05` | 3.4.4 |
| **`nixos-26.05`** (pinned channel) | **3.4.4** |

So advancing the pin today changes nothing. The fix is one branch hop from `release-26.05` and should reach `nixos-26.05` within days-to-two-weeks via the normal staging cycle, at which point the weekly `update-nixpkgs.yml` advance picks it up and these entries die on remediation rather than being renewed.

### Blast radius

PR CI is **not** blocked — `ci.yml` runs only `check-expirations`, not the gate (`ci.yml:425-441`). But `release.yml:884` carries a blocking `vulnix-gate` job, so **the release train is red** until this clears, and both nightly lanes re-open these issues every morning.

### Action

A time-boxed `.vulnixignore` block for the 8 blocking CVEs, expiring **2026-09-23** — its own Wednesday on the staggered grid (#1553), placed early because this block's remediation lever moves soonest of any in the register.

The reachability rationale is unusually strong for a register entry: **6 of the 8 are `rsyncd` daemon-mode only** (53791, 70461, 70463, 53802, 53784 — and 53803 scopes its own impact to setuid or privileged-daemon installs), and this image ships rsync as an interactive CLI and never runs a daemon. Only 70455 (receiver DoS from a malicious sender) and 53795 (`--temp-dir`/`--link-dest`, both caller-controlled) touch the actual usage model, and each requires the user to point rsync at a hostile peer.

Fix PR incoming; it refs this issue and #1593. Both close on the first green nightly.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 1, 2026 at 02:02 PM_

Still open, deliberately: the `main` lane is not fixed yet.

The rsync 3.5.0 advisory batch is excepted on `dev` only (#1594, `fc8c9e7f`) and #1593 is closed on that evidence. Replaying this run's own `main` artifact through the gate with `main`'s register still fails on all 8:

```
$ gh run download 33493764209 -n nix-image-cve-scan-main
$ git show origin/main:.vulnixignore > main.vulnixignore
$ uv run vulnix-gate vulnix-findings.json --register main.vulnixignore
::error:: CVE-2026-53791 / 53795 / 70461 / 70463 / 53803 / 70455 / 53784 / 53802 in rsync 3.4.4   (exit 1)
```

Nothing to do here on its own: the register reaches `main` with the next release train, and this closes when a scheduled `main` run passes after that. Tonight's run will re-file under this same title (dedup), which is the intended behaviour, not a new finding.

Note the ordering risk for whoever runs that train: the block expires **2026-09-23**, so if the pin advance to rsync 3.5.0 has already landed by then, drop the block instead of carrying it to `main`.

