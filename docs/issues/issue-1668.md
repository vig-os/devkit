---
type: issue
state: open
created: 2026-09-23T09:48:04Z
updated: 2026-09-23T12:59:53Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1668
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-23T14:38:46.188Z
---

# [Issue 1668]: [Nightly security scan (dev): unexcepted HIGH/CRITICAL vulnix findings](https://github.com/vig-os/devkit/issues/1668)

The nightly vulnix gate found **unexcepted HIGH/CRITICAL** CVEs in the `dev` Nix image closure (after `.vulnixignore`).

- **Scanned ref:** `dev`
- **Scan target:** flake `devkitImageEnv` (image package closure)
- **Scan date (UTC):** 2026-09-23T09:48:03Z
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35844608653
- **Findings artifact:** `nix-image-cve-scan-dev` on the run above (`vulnix-findings.json`, `vulnix-report.txt`)
- **Security tab:** https://github.com/vig-os/devkit/security

**To remediate:** advance the pinned nixpkgs rev if a fix has landed, or add a time-boxed `.vulnixignore` exception with a rationale (see `docs/CONTAINER_SECURITY.md`). Close this issue once a later scheduled run passes the gate.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 12:59 PM_

**Fix merged, awaiting the confirming scheduled run.**

The unbound exception landed on `dev` in #1670 (`b04a8ff5`): `CVE-2026-81642` is excepted to `2026-11-04`, with the provenance re-verified against the built runtime closure rather than inherited from the 2026-07-26 unbound block —

```
devcontainer-image-env -> podman 5.8.6 -> gpgme 2.0.1 -> gnupg 2.4.9
  -> gnutls 3.8.13 -> unbound-1.26.0-lib
```

`nix path-info -r` reports the `lib` output and nothing else, the env exposes no `unbound` executable, and `libgnutls-dane.so` is the only gnutls library referencing libunbound. The advisory's vector needs a resolver; this image ships none.

No pin lever exists: `nixos-26.05`, `staging-26.05` **and** `master` all still ship 1.26.0 with no CVE-named patch. Upstream fixed it in 1.26.1 (2026-09-16); [NixOS/nixpkgs#564725](https://github.com/NixOS/nixpkgs/pull/564725) merged to `staging` on 09-22 and the `staging-26.05` backport [NixOS/nixpkgs#565869](https://github.com/NixOS/nixpkgs/pull/565869) is still open — two branch hops away.

`vulnix-gate` re-run locally against this run's `dev` artifact goes from 1 unexcepted HIGH/CRITICAL to 0, 15 exceptions applied. Per this issue's own criterion, holding it open until a later **scheduled** run passes the gate on `dev` — next one 2026-09-24 05:00 UTC.

