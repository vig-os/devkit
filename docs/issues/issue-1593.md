---
type: issue
state: closed
created: 2026-09-01T09:49:01Z
updated: 2026-09-01T14:11:45Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1593
comments: 2
labels: security, security-scan
assignees: none
milestone: 1.13.0
projects: none
parent: none
children: none
synced: 2026-09-01T15:12:52.731Z
---

# [Issue 1593]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1593)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-01T09:48:59Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/33493764209
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 1, 2026 at 12:17 PM_

Same incident as #1592 — one root cause on both refs (`rsync-3.4.4`, 8 new unexcepted HIGH/CRITICAL CVEs from an overnight NVD feed publication, all fixed in rsync 3.5.0 which has not yet reached the pinned `nixos-26.05`).

Full diagnosis: https://github.com/vig-os/devkit/issues/1592#issuecomment-5493767806
Fix: #1594 (refs both issues).

Verified against this lane's own findings artifact (`nix-image-cve-scan-dev`): unexcepted HIGH/CRITICAL drops 8 → 0. Close on the first green nightly after merge.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 1, 2026 at 02:02 PM_

Fixed on `dev`: the rsync 3.5.0 advisory batch is excepted in the register (#1594, `fc8c9e7f`, merged 2026-09-01).

Verified against this run's own evidence rather than by inspection — replaying the artifact from the run that filed this issue through the current gate:

```
$ gh run download 33493764209 -n nix-image-cve-scan-dev
$ uv run vulnix-gate vulnix-findings.json --register .vulnixignore   # .vulnixignore at dev@2b7ae1fc
No unexcepted HIGH/CRITICAL findings (CVSS >= 7.0); 22 exception(s) applied
```

Same 8 findings, same closure, gate green. Tonight's scheduled dev lane is the formal re-confirmation; if anything differs it re-files under this same title rather than reopening.

The block is time-boxed to 2026-09-23 and must die on the pin advance that ships rsync 3.5.0 — it is one staging-next → release-26.05 → nixos-26.05 hop away, so the weekly `update-nixpkgs.yml` is expected to reach it well inside the window.

The `main` lane (#1592) stays open: the exception is not on `main` yet, and the same replay against `origin/main:.vulnixignore` still fails the gate on all 8 CVEs. It closes when the fix reaches `main` via the release train and a scheduled main run passes.

