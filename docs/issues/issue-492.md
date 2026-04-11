---
type: issue
state: closed
created: 2026-04-07T08:05:29Z
updated: 2026-04-07T09:26:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/492
comments: 0
labels: chore, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-11T04:27:31.793Z
---

# [Issue 492]: [[CHORE] Remove scheduled CI build+test from ci.yml](https://github.com/vig-os/devcontainer/issues/492)

### Chore Type

CI / Build change

### Description

The nightly CI schedule (`cron: '0 4 * * *'`) added in #461 rebuilds the container image from `dev` and runs all test suites daily. In practice this generates noise rather than signal.

**Why the current approach fails**

- Image tests assert on specific package versions and file checksums that are only valid at release time. A freshly built image pulls the latest upstream packages (e.g. `just 1.49.0` vs expected `1.48.x`), causing test failures that are not bugs — they are expected drift.
- The failing nightly run ([#482](https://github.com/vig-os/devcontainer/actions/runs/24066340992)) demonstrates this: 2 failures from version drift and CHANGELOG checksum mismatch, both non-actionable until the next release.
- Integration tests and project checks do not regress without code changes — there is nothing new to catch between PRs.
- Cost: ~7 min of CI time daily (~210 min/month) plus notification fatigue.

**Options evaluated**

| Option | Description | Verdict |
|--------|-------------|---------|
| **A. Status quo** (full nightly CI) | Rebuild image from `dev`, run all suites | High noise from version drift. Failures are not actionable. Not recommended. |
| **B. Nightly tests against published image** | Pull `:latest` from GHCR, run test suite | Tests already passed at release. No code changed, so functional tests will not suddenly fail. Very low value-add. Not recommended. |
| **C. Security-only nightly** | Remove `schedule` from `ci.yml`; keep `security-scan.yml` as-is | Catches the one thing that actually changes overnight (new CVE publications). Already implemented, green, cheap. **Recommended.** |

**Why Option C is sufficient**

- `security-scan.yml` already runs nightly at 05:00 UTC — pulls `:latest` from GHCR, runs Trivy, generates SBOM, uploads SARIF, auto-creates issues on fixable HIGH/CRITICAL findings.
- `codeql.yml` and `scorecard.yml` run weekly for source-level security.
- Python security (Bandit + Safety) runs on every PR — new advisories are caught when the next PR opens.
- Build breakage from upstream is caught at PR time, which is when it becomes actionable anyway.

### Acceptance Criteria

- [ ] Remove `schedule` trigger from `ci.yml`
- [ ] Remove the `schedule`-specific checkout ref logic (`github.event_name == 'schedule' && 'dev'`) from all jobs
- [ ] Update `ci.yml` header comments to remove nightly references
- [ ] Verify `security-scan.yml` continues running nightly unchanged
- [ ] Verify PR-triggered and manual-dispatch CI behavior is unchanged

### Implementation Notes

- In `ci.yml`: remove lines 39-41 (`schedule` trigger) and the ternary `ref: ${{ github.event_name == 'schedule' && 'dev' || github.ref }}` in checkout steps (lines 69, 123, 151, 188, 206, 266) — simplify to just `${{ github.ref }}` (or remove the `ref` key entirely since `github.ref` is the default).
- No changes needed to `security-scan.yml`, `codeql.yml`, or `scorecard.yml`.

### Related Issues

Reverses the nightly CI portion of #461. The security scan portion of #461 (`security-scan.yml` upgrade to nightly) remains unchanged and is working well.

### Priority

Medium

### Changelog Category

No changelog needed

### Additional Context

- Failing run: https://github.com/vig-os/devcontainer/actions/runs/24066340992
- Nightly history: 2/5 recent scheduled CI runs failed from upstream drift (Apr 6-7), while `security-scan.yml` has been green for 5+ consecutive runs.

