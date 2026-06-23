---
type: issue
state: open
created: 2026-06-23T06:54:12Z
updated: 2026-06-23T06:54:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/637
comments: 0
labels: docs, area:image, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:48.662Z
---

# [Issue 637]: [T3.1 — vulnix + SBOM CVE scanning; re-author security policy](https://github.com/vig-os/devcontainer/issues/637)

Tracking: #625



## Context

A Nix-built image has no apt/dpkg database, so Trivy's OS-package scanner — the basis of the
current CVE workflow and the `.trivyignore` expiry register — goes dark. This is the headline
cost of the image cutover and must be addressed *before* publishing (#639). The signal is
replaced with `vulnix` (a nixpkgs-native CVE scanner) plus SBOM-based scanning.

## Scope

**In:**
- Make **`vulnix`** the primary nightly CVE scanner.
- Keep Trivy in **CycloneDX SBOM mode** for defense-in-depth.
- Rewrite `docs/CONTAINER_SECURITY.md`: drop the apt `--only-upgrade` escape hatch; the CVE
  lever becomes "advance the nixpkgs rev".
- Rebuild the **exception register with expiry** around vulnix findings to preserve the
  IEC 62304 audit story.

**Out:**
- Renovate wiring for `flake.lock` (#638).

## Tasks

- [ ] Add a `vulnix` nightly scan job
- [ ] Emit a CycloneDX SBOM and feed Trivy in SBOM mode
- [ ] Rewrite `docs/CONTAINER_SECURITY.md`
- [ ] Rebuild the exception register with expiry around vulnix findings

## Acceptance criteria

- `vulnix` nightly runs.
- Rewritten policy + expiry register reviewed.
- **Objective gate (this is the go/no-go input for #639):** no HIGH/CRITICAL vulnix finding on
  the Nix image without a documented, expiring entry in the exception register.
- **Confidence check (not a pass/fail gate):** Trivy-vs-vulnix findings compared over a
  one-cycle overlap and the diff archived, to confirm no class of finding silently disappears
  in the scanner switch. The two scanners cover different surfaces (apt packages vs Nix store),
  so this is a documented comparison, not a numeric parity requirement.

## Dependencies

- **Depends-on:** #634.
- **Blocks:** #639.

## Files

- `.github/workflows/security-scan.yml`
- `docs/CONTAINER_SECURITY.md`
- exception register (replacement for `.trivyignore` semantics)

## Test notes

- The objective threshold (no unexcepted HIGH/CRITICAL) is the explicit gate input for #639;
  the Trivy-vs-vulnix overlap diff is archived as supporting confidence evidence.

## Related issues

- **#604** (consolidate Trivy scan categories / clean stale alerts) — its "single authoritative
  scan + document the SSoT" goal **is** this issue's outcome under vulnix/SBOM. The
  orphaned/stale-alert cleanup (the `container-image-scheduled` and stale `container-image`
  categories) should still happen so zombies aren't carried into the new system.
- **#602 / #521** (nightly HIGH/CRITICAL gate issues) — these gates re-point from Trivy-on-apt
  to vulnix; the apt-CVE surface they track changes with the Nix image. #521 (Apr) is already
  stale vs #602 (Jun). Close once the new scan passes its gate (with #642).
- **#109** (discussion: full security scan on every PR) — the category-consolidation decision
  overlaps this thread; resolve together.
- **#27** (Adopt Nix/devenv) — provides the SBOM / IEC 62304 / air-gapped framing this issue
  realizes (`nix derivation show`, `nix flake archive`).

