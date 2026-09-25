---
type: issue
state: closed
created: 2026-09-23T09:48:19Z
updated: 2026-09-25T06:23:48Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1669
comments: 2
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-25T07:32:57.489Z
---

# [Issue 1669]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1669)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-23T09:48:18Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35844608653
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 01:00 PM_

**Still open — `main` has neither the exception nor the closure change.**

The unbound exception landed on `dev` in #1670 (`b04a8ff5`); see #1668 for the triage, the re-verified provenance and the upstream lever status. `main`'s register carries no `CVE-2026-81642` entry and `main`'s closure still ships unbound 1.26.0, so its nightly lane stays red until a release train carries the register over.

Unlike #1668, this one cannot be cleared by the next scheduled run alone — it is gated on the same 1.16.0 train as #1667.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 24, 2026 at 11:19 AM_

**Second feed event on the same upstream release — fix open in #1675, this issue stays open.**

The confirming run for the 2026-09-23 fix ([run 35982816399](https://github.com/vig-os/devkit/actions/runs/35982816399)) went red again on both lanes, same package, two CVEs the previous exception did not carry: `CVE-2026-82717` (9.8) and `CVE-2026-81634` (7.5).

**Not a regression and not a closure change.** All three unbound CVEs — `-81642` plus these two — were published **2026-09-16** and are fixed by the same **1.26.1** release. They arrived a day apart because vulnix matches on CPE and NVD's analysis lagged:

| CVE | CPE analysed (`lastModified`) | Visible to |
|---|---|---|
| `CVE-2026-81642` | in time for 09-23 | the 09-23 scan |
| `CVE-2026-82717` | `2026-09-23T19:50Z` | the 09-24 scan |
| `CVE-2026-81634` | `2026-09-23T19:51Z` | the 09-24 scan |

Both additions landed their CPE ~10h *after* the 09-23 09:43Z scan and ~14h before the 09-24 09:42Z one. The 2026-09-23 triage was therefore not incomplete — it excepted every member of the batch that existed as a CPE match at the time.

Re-confirmed as a feed event on the same evidence shape: `flake.lock` unchanged since the 2026-09-21 pin advance (#1662) and byte-identical on both refs, the register byte-identical on both refs, the 09-21 and 09-22 scans green on these same closures, nearest grid date 2026-10-07 so nothing expired.

**Reachability unchanged** — both are resolver paths (`-81634` RRSet canonicalisation, `-82717` CNAME synthesis on an upstream response), and this closure still carries `libunbound` only via gnutls DANE, no daemon, no `unbound` binary.

**The lever shortened:** the `staging-26.05` backport ([NixOS/nixpkgs#565869](https://github.com/NixOS/nixpkgs/pull/565869)) has since **merged**, so `staging-26.05` and `staging` carry 1.26.1 while `nixos-26.05` and `master` still ship 1.26.0 — one `staging` → `nixos-26.05` cycle away rather than two branch hops. The `2026-11-04` date is deliberately unchanged; all three CVEs share one death condition and should be deleted together on the advance that ships 1.26.1.

Verified by replaying this run's own findings artifacts through `vulnix-gate`: **2 unexcepted HIGH/CRITICAL → 0 on both `main` and `dev`**, exit 1 → exit 0.


