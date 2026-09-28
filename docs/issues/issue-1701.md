---
type: issue
state: closed
created: 2026-09-25T08:46:43Z
updated: 2026-09-25T15:07:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1701
comments: 2
labels: chore, priority:medium, area:ci, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:43.201Z
---

# [Issue 1701]: [[CHORE] Take Security Scan off the CI critical path](https://github.com/vig-os/devkit/issues/1701)

### Chore Type

CI / Build change

### Description

Once #1692 splits `Project Checks` into lanes (longest lane ≈ 4m39s), the whole-run critical path moves to `Build Container Image` → `Security Scan`. Measured on run [36108278820](https://github.com/vig-os/devkit/actions/runs/36108278820) (job `Security Scan`):

| Step | Time |
|---|---|
| setup-env | 42s |
| download image artifact | 6s |
| Report HIGH/CRITICAL/MEDIUM (trivy image, non-blocking) | **2m54s** |
| Generate container SBOM (trivy image --format cyclonedx) | **2m32s** |
| job total | 6m26s |

Plus `build-image` at 1m57s ahead of it: **8m25s** end to end, against ≈ 4m39s for the next-longest chain after #1692.

The two trivy steps are independent and each re-parses the same 1.5 GiB image tarball; nothing in the job depends on the other step's output. The vulnerability report is explicitly non-blocking awareness (the authoritative CVE gate is the nightly vulnix lane in `security-scan.yml`).

### Acceptance Criteria

- [ ] `Security Scan` no longer sits on the run's critical path, or the path is ≤ the longest project lane: measure before/after on a warm run and record it in the PR body
- [ ] The SBOM artifact (`sbom-<version>-amd64`, CycloneDX) and the non-blocking HIGH/CRITICAL/MEDIUM report keep their names and content
- [ ] `.trivyignore`/`.vulnixignore` expiration validation still runs in PR CI
- [ ] `summary` covers any new job

### Implementation Notes

Options, cheapest first — measure before choosing:

1. **Scan the SBOM, not the image, for the vulnerability report**: generate the CycloneDX SBOM once (2m32s), then `trivy sbom sbom-cyclonedx.json` for the report — seconds, since the image parse is the cost. One trivy install, one image parse.
2. **Two parallel jobs** (`sbom`, `vuln-report`), each downloading the artifact: path becomes build + max(2m54, 2m32) + setup ≈ 5m30s. Doubles runner minutes (unmetered, public repo).
3. **Trivy DB cache**: the job header already notes `trivy-action` caches the DB in `$GITHUB_WORKSPACE/.cache/trivy`; check whether the cache actually hits across runs (`actions/cache` key) — a cold DB pull is part of the 2m54s.

Option 1 changes what the report scans (SBOM-derived vs image-derived findings); verify the finding set is identical on the same image before switching.

### Related Issues

- Predicted by #1687 and #1692 as the next bottleneck after the project-checks split
- Nightly authoritative gate: `security-scan.yml` (vulnix)

### Priority

Medium

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: option 1, measured

Timings on the four most recent `dev` CI runs (36124206119, 36120369838, 36119970797, 36108278820) are stable: build-image 110-119 s, Security Scan 336-419 s (vuln report 140-174 s, SBOM 122-152 s, setup-env 42 s). Critical path on 36124206119 = 110 + 419 = **529 s**; the longest project lane after #1692 is 244-288 s.

- **Option 3 is a no-op.** The trivy DB cache already hits (`Cache restored from key: cache-trivy-2026-09-25`, 4 s) in both steps, and so does the binary cache (`trivy-binary-v0.74.0-Linux-X64`). The time is the 1.5 GiB tarball walk (`Running Trivy with options: trivy image .` → 163 s; secret scanning is only ~15 s of it). Remove a walk, don't trim scanners.
- **Option 1 is already proven in this repo.** `security-scan.yml` generates the CycloneDX SBOM and then runs `scan-type: sbom` for its table view: on nightly run 36121477017 the SBOM step took 136-160 s and the SBOM-mode scan **12 s**.
- Trivy SBOM scanning covers vulnerabilities and licenses only, so the PR-CI report loses the secret scanner. The `.trivyignore` register's own RETIRED block records that the secret scanner runs over this image and finds nothing, and the report is non-blocking awareness. Accepted; an image-mode `--scanners secret` pass can join the nightly (which already builds the tar) as a follow-up if wanted.
- `trivy convert` (single JSON scan with `--list-all-pkgs` → table + CycloneDX) would keep secrets but the action has no convert scan-type and the converted CycloneDX has a history of schema complaints (aquasecurity/trivy #4900, #3663), threatening the SBOM artifact's content criterion. Kept as the fallback only.

**Plan:** swap the two steps (SBOM first, then `scan-type: sbom` / `scan-ref: sbom-cyclonedx.json` with the same severity, `exit-code: 0` and `trivyignores`), artifact name and content unchanged; move `check-expirations` into `python-security` (already has setup-env + uv sync, no `build-image` dependency) so `security-scan` drops its 42 s setup-env; no new job, so `summary` and its shape test are untouched. The PR carries a one-off equivalence step diffing `[VulnerabilityID, PkgName, InstalledVersion]` between `trivy image --format json` and `trivy sbom --format json` on the same tarball, with the diff and before/after timings in the PR body. Expected path ≈ 110 + 185 ≈ **295 s**, under the longest lane.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 03:07 PM_

Done in #1714, merged to `dev` (45958522). Measured on run 36151221572: `Security Scan` 170 s (was 336-419 s), report step 3 s (was 140-174 s), critical path 282 s against 353 s for the longest project lane.

