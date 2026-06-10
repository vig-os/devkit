# Container Security Patching Strategy

This document describes how the devcontainer image handles system-level
security vulnerabilities (CVEs) in OS packages.

## Principles

1. **Reproducibility first** – Every build from the same commit must produce
   the same image. Non-deterministic operations (`apt-get upgrade`) are
   forbidden in the default build path.
2. **Defence in depth** – Multiple layers detect and remediate CVEs at
   different speeds so that no single mechanism is a bottleneck.
3. **Minimal blast radius** – When manual patching is necessary, only the
   specific vulnerable package is upgraded, and the change is traceable to a
   CVE identifier.

## Layers of defence

### 1. Base image digest pinning (primary)

The `FROM` line in the Containerfile pins the base image to an immutable
SHA-256 digest:

```dockerfile
FROM python:3.14-slim-bookworm@sha256:<digest>
```

Renovate (configured with the `dockerfile` manager in `renovate.json`) monitors
the upstream image and opens a pull request whenever a new digest is published.
Because the upstream maintainers rebuild the image to include Debian security
patches, most CVEs are resolved simply by merging the Renovate PR.

**Typical remediation time:** 1–7 days after the upstream image is rebuilt.

### 2. Nightly Trivy scan (detection)

The scheduled workflow (`.github/workflows/security-scan.yml`) pulls the
published `:latest` image nightly (05:00 UTC) and runs a full Trivy vulnerability
scan. Results are:

- Printed as a table in the workflow log.
- Uploaded as a SARIF report to the GitHub Security tab.
- Accompanied by a CycloneDX SBOM artifact.

This scan is **non-blocking** for the full report (exit-code 0) and serves as
an early-warning system for newly published CVEs. A separate gate step fails
on fixable HIGH/CRITICAL findings (`ignore-unfixed: true`).

### 3. Targeted package upgrades (escape hatch)

When a HIGH or CRITICAL CVE is detected that:

- Has a fix available in the Debian stable repository, **and**
- Cannot wait for the next base image rebuild (e.g., actively exploited),

a targeted upgrade is added to the Containerfile:

```dockerfile
RUN apt-get update && apt-get install -y --only-upgrade \
    libfoo=1.2.3-1+deb12u1 \  # CVE-2026-XXXXX
    && apt-get clean && rm -rf /var/lib/apt/lists/*
```

Rules for targeted upgrades:

| Rule | Rationale |
|------|-----------|
| Each package must reference a CVE in a comment | Auditability |
| Pin the package to an exact version | Reproducibility |
| Remove the entry once the base image digest includes the fix | Avoid drift |
| Never use blanket `apt-get upgrade` or `dist-upgrade` | Reproducibility |

### 4. Trivy ignore list (risk acceptance)

Low-risk CVEs that are not exploitable in the devcontainer context are
documented in `.trivyignore` with:

- A risk assessment explaining why the CVE is acceptable.
- An expiration date after which the entry must be re-evaluated.
- A link to the tracking issue.

Expired entries fail CI via `check-expirations` (pre-commit hook and CI
workflows), forcing periodic review consistent with the IEC 62304 exception
register model.

As of the next release image (Debian 12.14 base), 78 unfixed LOW CVEs in OS
packages are accepted in `.trivyignore` with expiration 2026-12-01. These
have no available Debian patch; the nightly gate only fails on fixable
HIGH/CRITICAL findings. Re-scan after each base-image digest bump and drop
entries when Debian ships fixes. Tracking: #566, #512, #521.

## Why not `apt-get upgrade`?

Running `apt-get upgrade` (or `dist-upgrade`) in the Containerfile has several
drawbacks:

| Problem | Explanation |
|---------|-------------|
| **Non-reproducible builds** | The same Containerfile produces different images on different days because the Debian mirror contents change constantly. |
| **Defeats digest pinning** | The digest guarantees a known starting point; upgrading everything immediately discards that guarantee. |
| **Untraceable changes** | There is no record of *which* packages changed or *why*. A targeted upgrade with a CVE comment is auditable. |
| **`dist-upgrade` risk** | `dist-upgrade` can remove packages or change dependencies, potentially breaking the image silently. |
| **Cache invalidation** | A blanket upgrade invalidates the Docker layer cache on every build, increasing build times. |

## Decision flow

```
New CVE detected by Trivy
        │
        ▼
 Is severity HIGH or CRITICAL?
        │
   No ──┤──── Yes
   │         │
   ▼         ▼
 Add to    Is a fix available in Debian stable?
 .trivyignore    │
 (with risk   No ──┤──── Yes
 assessment)  │         │
              ▼         ▼
           Add to    Can it wait for a base image rebuild?
           .trivyignore    │
           (with risk   No ──┤──── Yes
           assessment)  │         │
                        ▼         ▼
                   Add targeted   Wait for Renovate
                   --only-upgrade   digest update PR
                   to Containerfile
```

## References

- [Containerfile](../Containerfile) – Build definition with inline comments
- [.trivyignore](../.trivyignore) – Accepted low-risk CVEs
- [security-scan.yml](../.github/workflows/security-scan.yml) – Nightly scan workflow
