---
type: issue
state: closed
created: 2026-09-16T09:43:25Z
updated: 2026-09-16T17:48:24Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1636
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T07:29:37.303Z
---

# [Issue 1636]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1636)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-16T09:43:23Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35080687787
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 16, 2026 at 05:48 PM_

Resolved on `dev` by #1638 (merged as 3d1d127b).

**Diagnosis.** A feed event, not a closure change. The 09-15 run
(`34954313210`) was green on the same pin the 09-16 run (`35080687787`) failed
on, and the findings delta is **8 added / 0 removed against exactly one
package**, with no expiry fired — the libxml2 `CVE-2026-8613x`/`-8614x` batch
reached the NVD feed in that window.

Of the eight, only `CVE-2026-86140` crosses the gate's 7.0 threshold and takes a
register entry; the other seven score 2.9–6.9 and are deliberately left out. The
defect is a `strcat` stack overflow in `xmlSnprintfElements` (`valid.c`),
reachable only while formatting a validity error for a DTD-validated document,
and scored local-vector by both NVD (8.0) and the NIST analyst (7.8). libxml2 is
a transitive dependency here and nothing validates untrusted XML against a DTD.

**Evidence for closing now rather than waiting for a nightly** — the #1593
precedent. Replaying this run's own artifact against the merged `dev` register:

```
$ uv run vulnix-gate vulnix-findings.json --register .vulnixignore   # origin/dev
No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 31 exception(s) applied
```

Note PR CI never runs `vulnix-gate` (`ci.yml:440` — the authoritative gate is
the nightly `security-scan.yml`; PR CI runs only `check-expirations`), so this
replay, not the green PR, is the evidence.

**Exit condition.** The block expires 2026-10-28 but should not reach it:
libxml2 2.15.4 is in `staging-26.05` and `staging-next-26.05`, riding the same
open iteration-7 PR (`NixOS/nixpkgs#563094`) as curl 8.22.0 and openssl 3.6.4.
One advance should clear all three blocks, which should then be **deleted**
rather than renewed.

`main` (#1637) stays open: its register only moves via a release train.

