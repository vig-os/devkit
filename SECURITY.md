# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |
| < latest | No       |

Only the latest released version receives security updates.
Older versions are not maintained.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, use
[GitHub Private Vulnerability Reporting](https://github.com/vig-os/devkit/security/advisories/new).

When reporting, please include:

- Description of the vulnerability
- Steps to reproduce (or proof of concept)
- Affected component (container image, CI workflow, build script, etc.)
- Potential impact assessment

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgement | 3 business days |
| Initial assessment | 7 business days |
| Fix or mitigation | 30 calendar days |

We will keep you informed of progress throughout.

## Scope

The following areas are in scope for security reports:

- **Supply chain:** GitHub Actions workflows and pinned dependencies
- **Container image:** Base image vulnerabilities, installed packages, permissions
- **Build tooling:** Scripts in `scripts/`, `install.sh`, `init-workspace.sh`
- **Secrets handling:** Accidental exposure of tokens, keys, or credentials
- **Workflow permissions:** Overly broad permissions in CI/CD pipelines

## Security Practices

This repository follows these security practices:

- All GitHub Actions are pinned to commit SHAs (not mutable tags)
- Pre-commit hook repos are pinned to commit SHAs
- The container image is built reproducibly with Nix (`dockerTools.buildLayeredImage`) from a pinned `nixpkgs` revision in `flake.lock`
- Dependabot monitors dependencies for known vulnerabilities
- Dependency review blocks PRs that introduce vulnerable dependencies
- The container image is scanned nightly with `vulnix` (Nix store closure), plus a CycloneDX SBOM and a Trivy SBOM-mode scan (see `docs/CONTAINER_SECURITY.md`)
- SBOM (SPDX) is generated and attested for every release
- Released container images are signed with Sigstore cosign (keyless)
- SLSA build provenance attestations are attached to released images
- Workflow permissions follow the principle of least privilege
- Workflow inputs are bound to environment variables (not interpolated inline)
- No `pull_request_target` triggers are used (prevents untrusted code execution)
- OpenSSF Scorecard runs weekly to track security posture
- CodeQL static analysis scans Python build tooling and GitHub Actions workflows
- Branch protection is enforced via GitHub Enterprise rulesets (Main protection requires pull request review, code-owner approval, required status checks, non-fast-forward merges, and branch deletion protection)

### OpenSSF Scorecard accepted findings

The following Scorecard checks are not applicable to a devcontainer image repository and are accepted as won't-fix:

- **FuzzingID** (medium): no fuzzing targets in container build tooling or CI scripts
- **CIIBestPracticesID** (low): not a CII Best Practices badge candidate; posture is tracked via Scorecard and CodeQL instead

**VulnerabilitiesID** (high) is a roll-up of container and dependency findings remediated separately (see `.vulnixignore`, `.trivyignore`, and dependency review).

## Compliance

This project is designed to support medical device software development under
IEC 62304 and ISO 13485. Security practices align with configuration management
and risk management requirements of these standards.

## Known Vulnerability Exceptions

This project accepts and documents known vulnerabilities through
expiration-enforced exception registers (`.vulnixignore`, `.trivyignore`, and
`.github/dependency-review-allow.txt`). These exceptions follow an IEC 62304
medtech-compliant risk assessment model. Expired entries fail CI via the
`check-expirations` utility (pre-commit hook and CI workflows).

### Container Image CVEs (`vulnix` / Trivy Exceptions)

The image is Nix-built (`dockerTools.buildLayeredImage`) from a pinned `nixpkgs`
revision, so its CVE surface is the package closure of that revision. The nightly
`vulnix` scan (`.github/workflows/security-scan.yml`) gates HIGH/CRITICAL findings
(CVSS v3 ≥ 7.0) against the `.vulnixignore` register, and a CycloneDX SBOM + Trivy
SBOM-mode scan provides an independent second view. The primary remediation lever
is advancing the pinned `nixpkgs` revision (Renovate `nix` manager + weekly
`lockFileMaintenance`). Findings that are not exploitable in the devcontainer
context — or that `vulnix` reports despite a `nixpkgs` backport — are accepted in
`.vulnixignore` / `.trivyignore` with a rationale and an expiration. See
[`docs/CONTAINER_SECURITY.md`](docs/CONTAINER_SECURITY.md) for the full strategy
and decision flow.

### Test Dependency Vulnerabilities (GHSA Exceptions)

CI-only npm dependencies are minimal (`@devcontainers/cli`); the BATS test
framework and its helpers are now provided by the Nix toolchain (`flake.nix`)
rather than npm, removing the legacy transitive advisory surface. The sole
standing `dependency-review` exception is a documented false positive:

- **bats-file** (GHSA-wvrr-2x4r-394v): the advisory flags the npm-registry
  `bats-file@0.2.0` as malware; the project installs from the official GitHub
  source (`github:bats-core/bats-file#v0.4.0`), whose `package.json` simply never
  bumped its version field. Tracked in `.github/dependency-review-allow.txt` with
  an expiration.

Production deployments do not include or execute any test dependencies.
