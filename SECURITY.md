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
[GitHub Private Vulnerability Reporting](https://github.com/vig-os/devcontainer/security/advisories/new).

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
- Docker base image is pinned to digest in the Containerfile
- Dependabot monitors dependencies for known vulnerabilities
- Dependency review blocks PRs that introduce vulnerable dependencies
- Container images are scanned for vulnerabilities (Trivy) in CI and release
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

**VulnerabilitiesID** (high) is a roll-up of container and dependency findings remediated separately (see `.trivyignore` and dependency review).

## Compliance

This project is designed to support medical device software development under
IEC 62304 and ISO 13485. Security practices align with configuration management
and risk management requirements of these standards.

## Known Vulnerability Exceptions

This project accepts and documents known vulnerabilities in test-only dependencies
through expiration-enforced exception registers (`.github/dependency-review-allow.txt`
and `.trivyignore`). These exceptions follow an IEC 62304 medtech-compliant risk
assessment model:

### Test Dependency Vulnerabilities (GHSA Exceptions)

Nine vulnerabilities have been accepted in unmaintained legacy BATS test framework
dependencies (bats-assert, verbose, reconnect, request, sockjs, engine.io, engine.io-client):

- **engine.io** (GHSA-r7qp-cfhv-p84w): Uncaught exception leading to DoS
- **engine.io** (GHSA-j4f2-536g-r55m): Resource exhaustion via large messages
- **debug** (GHSA-gxpj-cx7g-858c): Regular Expression Denial of Service (ReDoS)
- **node-uuid** (GHSA-265q-28rp-chq5): Insecure entropy source (Math.random())
- **qs** (GHSA-6rw7-vpxm-498p): DoS via memory exhaustion (arrayLimit bypass)
- **tough-cookie** (GHSA-72xf-g2v4-qvf3): Prototype Pollution
- **ws** (GHSA-6663-c963-2gqg): DoS via large websocket messages
- **ws** (GHSA-5v72-xg48-5rpm): Denial of Service via malformed frames
- **ws** (GHSA-2mhh-w6q8-5hxw): Remote memory disclosure

**Risk Assessment:** All are HIGH or MODERATE severity vulnerabilities from packages
last updated 5-10+ years ago. Impact is **isolated to CI/development environment**
with **no runtime production code exposure**. Expiration dates (2026-11-17) enforce
periodic re-evaluation and investigation of BATS framework modernization.

**Mitigation:** These dependencies are transitive and only used in the test pipeline.
Production deployments do not include or execute any test dependencies.
