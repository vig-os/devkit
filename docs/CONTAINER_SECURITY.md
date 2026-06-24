# Container Security Patching Strategy

This document describes how the devcontainer image handles software
vulnerabilities (CVEs).

The image is a **Nix-built image** (`dockerTools.buildLayeredImage`, see
`flake.nix`). This document describes the **Nix posture** — the mechanisms now in
place. The Debian/`apt` build path has been decommissioned (#642).

## Principles

1. **Reproducibility first** – Every build from the same commit and the same
   `flake.lock` produces a byte-identical image closure. There is no
   non-deterministic upgrade step (no `apt-get upgrade`) in the build path.
2. **Defence in depth** – Multiple scanners and levers detect and remediate CVEs
   at different speeds and over different surfaces so no single mechanism is a
   bottleneck.
3. **Minimal blast radius** – When a CVE must be remediated out-of-band, the
   change is the smallest pin that fixes it and is traceable to a CVE identifier.

## Layers of defence

### 1. Pinned `nixpkgs` revision (primary)

The toolchain and the image contents come from a single pinned `nixpkgs`
revision in `flake.lock`. Because the closure is fully pinned, the CVE surface
is exactly what that revision ships. Renovate keeps the pin current through two
mechanisms in `renovate.json`:

- The **`nix` manager** detects flake inputs and proposes pinned-input updates.
- **`lockFileMaintenance`** (enabled, scheduled weekly) refreshes the locked
  revisions of all inputs (notably `nixpkgs`) so upstream security fixes land
  through the normal PR/CI gate rather than a manual `nix flake update`.

**Typical remediation time:** within the weekly `lockFileMaintenance` cycle, or
immediately by merging an out-of-cycle `nixpkgs`-bump PR.

### 2. Nightly `vulnix` scan (primary detection)

The scheduled workflow (`.github/workflows/security-scan.yml`, job
`scan-nix-image`) builds the image's package closure (the flake
`devcontainerImageEnv` target) nightly and runs **`vulnix`**, the nixpkgs-native
CVE scanner. A Nix image has no `apt`/`dpkg` database, so Trivy's OS-package
scanner goes dark; `vulnix` matches the Nix store closure against the NVD feeds
instead.

- HIGH/CRITICAL findings (CVSS v3 ≥ 7.0) are gated by `vulnix-gate`
  (`packages/vig-utils`) against the `.vulnixignore` exception register; a
  finding blocks only when it is **not** covered by a non-expired exception.
- Sub-threshold and unscored CVEs are awareness-only and never gate.

> **`vulnix` over-reporting.** `vulnix` matches by package name + *upstream*
> version and does not see `nixpkgs`' backported security patches, so it reports
> CVEs already fixed in the shipped derivation. The primary lever is therefore to
> advance the `nixpkgs` rev (layer 1); genuinely-not-applicable findings are
> accepted in `.vulnixignore` with a rationale (layer 5).

During the discovery phase the gate is **non-blocking** (`continue-on-error`).
The publish-cutover (#639) flips it to blocking and wires SARIF upload and a
deduplicated issue.

### 3. CycloneDX SBOM + Trivy SBOM-mode scan (defence in depth)

The same nightly job emits a **CycloneDX SBOM** of the Nix image (via Trivy) and
runs Trivy in **SBOM-scan mode** over it for a second, independent vulnerability
view. `vulnix` (Nix store closure) and Trivy (SBOM components) cover different
surfaces, so both outputs are uploaded as an artifact to support a
`vulnix`-vs-Trivy overlap comparison (confidence evidence, not a numeric-parity
gate).

### 4. Advance the `nixpkgs` rev (remediation lever)

When a HIGH/CRITICAL CVE is real (not a `vulnix` false positive) and fixed
upstream:

- **Preferred:** bump the pinned `nixpkgs` rev (merge the Renovate
  `nix`-manager / `lockFileMaintenance` PR, or open an out-of-cycle bump) so the
  patched derivation enters the closure. This is reproducible and is captured by
  the PR/CI gate.
- **Rare escape hatch:** if only some inputs can move, pin the single patched
  package through a flake overlay, referencing the CVE in a comment, and remove
  the override once the base `nixpkgs` rev includes the fix.

| Rule | Rationale |
|------|-----------|
| Reference the CVE in the PR / overlay comment | Auditability |
| Move the smallest pin that fixes it | Minimal blast radius |
| Remove an overlay override once `nixpkgs` ships the fix | Avoid drift |
| Never disable the pin to "take latest everything" | Reproducibility |

**Compensating control — `vulnix` before/after diff.** A `nixpkgs` revision bump
does not declare *which* CVE it fixes (the `nix` manager reports only the
old → new git revision). To keep the audit trail, each `flake.lock` /
`nixpkgs`-bump PR should include a `vulnix` scan diff taken **before and after**
the bump, showing which advisories the new revision clears (or introduces).

### 5. Exception registers (risk acceptance)

CVEs that are not exploitable in the devcontainer context, or are `vulnix`
false positives (already patched in `nixpkgs`), are accepted in an exception
register with:

- A risk assessment / rationale (patched-in-nixpkgs, not-exploitable, or
  awaiting-upstream).
- An expiration date after which the entry must be re-evaluated.
- A link to the tracking issue.

Two registers share one format and one validator:

- **`.vulnixignore`** — `vulnix` findings on the Nix image (consumed by
  `vulnix-gate`).
- **`.trivyignore`** — image-agnostic Trivy findings on the Nix image (bundled-
  binary CVEs) and Trivy secret-scan false positives.

Both use the `Expiration: YYYY-MM-DD` directive format and are validated by
`check-expirations` (pre-commit hook and CI). Expired entries fail CI, forcing
periodic review consistent with the IEC 62304 exception-register model.

## Why pin `nixpkgs` (and not track an unpinned channel)?

Building from an unpinned/rolling input has the same drawbacks the old
`apt-get upgrade` escape hatch had:

| Problem | Explanation |
|---------|-------------|
| **Non-reproducible builds** | The same flake produces different closures on different days as the channel moves. |
| **Defeats pinning** | The lock guarantees a known closure; tracking latest immediately discards that guarantee. |
| **Untraceable changes** | There is no record of *which* packages changed or *why*. A pinned bump with a `vulnix` diff is auditable. |
| **Cache invalidation** | A wholesale input move rebuilds (and re-pushes) the entire closure on every build. |

## Decision flow

```
New CVE reported by vulnix (Nix image)
        │
        ▼
 Is severity HIGH or CRITICAL (CVSS v3 >= 7.0)?
        │
   No ──┤──── Yes
   │         │
   ▼         ▼
 Awareness  Is it real (not already patched in nixpkgs / not a vulnix FP)?
 only            │
            No ──┤──── Yes
            │         │
            ▼         ▼
   Accept in      Is the fix available upstream in a newer nixpkgs?
   .vulnixignore       │
   (patched-in-    No ──┤──── Yes
   nixpkgs,        │         │
   with expiry)    ▼         ▼
              Accept in   Advance the nixpkgs rev
              .vulnixignore  (Renovate bump / overlay
              (awaiting-      pinning the patched pkg)
              upstream,
              with expiry)
```

## References

- [flake.nix](../flake.nix) – Nix image (`devcontainerImage`), scan target
  (`devcontainerImageEnv`), and pinned `vulnix`
- [.vulnixignore](../.vulnixignore) – Accepted `vulnix` findings (Nix image)
- [.trivyignore](../.trivyignore) – Accepted Trivy findings (Nix image, image-agnostic)
- [security-scan.yml](../.github/workflows/security-scan.yml) – Nightly scan workflow
- `vulnix-gate` / `check-expirations` (`packages/vig-utils`) – Gate and expiry validators
