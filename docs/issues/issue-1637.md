---
type: issue
state: open
created: 2026-09-16T09:44:16Z
updated: 2026-09-16T17:48:54Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1637
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T07:29:36.768Z
---

# [Issue 1637]: [Nightly security scan (main): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1637)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `main` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `main`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-16T09:44:15Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35080687787
- **Findings artifact:** `nix-image-cve-scan-main` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 16, 2026 at 05:48 PM_

Diagnosed and fixed on `dev` by #1638 (merged as 3d1d127b). **Staying open**:
the fix has not reached `main` yet.

**Same incident as #1636** — one feed event, both refs. The 09-15 run
(`34954313210`) was green on the same pin the 09-16 run (`35080687787`) failed
on; the delta is 8 added / 0 removed against one package, identical on both
lanes. The sole blocker is `CVE-2026-86140` (libxml2 2.15.3, NVD 8.0 /
NIST analyst 7.8, local-vector): a `strcat` stack overflow in
`xmlSnprintfElements` reachable only while formatting a validity error for a
DTD-validated document. Full rationale in the register and in #1636.

**Why this cannot be closed yet.** `main` still carries the pre-#1638 register:

```
$ git show origin/main:.vulnixignore | grep -c '^CVE-2026-86140'
0
```

Replaying this run's `main` artifact against `main`'s own register still fails
on `CVE-2026-86140`. Against the merged `dev` register the same artifact is
green (31 exceptions applied), so the fix is correct for `main`'s closure — it
simply is not on `main`.

`main`'s register only moves via a release train: `update-nixpkgs.yml` targets
`dev` only, and `prepare-hotfix.yml` is not on `main` yet (#1623, unreleased).
This is the #1592 precedent exactly.

**Closes when** the next release train carries the register to `main` and the
first `main` nightly after it is green. The `main` lane stays red until then;
that is expected and is not a second defect.

