---
type: issue
state: closed
created: 2026-06-09T08:24:06Z
updated: 2026-06-09T10:58:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/562
comments: 0
labels: priority:high, area:ci, effort:medium, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:25.178Z
---

# [Issue 562]: [security(ci): resolve repo-owned workflow findings (Scorecard DangerousWorkflow + stale CodeQL permissions + posture)](https://github.com/vig-os/devcontainer/issues/562)

## Bucket A - Repo-owned config findings

The only Security-tab findings that live in **this repo's own code/config** (everything else is upstream container packages). Verified against `dev` on 2026-06-09.

### A1. Scorecard CRITICAL - DangerousWorkflowID (alert #1748)
- File: `.github/workflows/renovate-changelog.yml`
- Scorecard flags `pull_request_target` combined with checkout of the PR head SHA.
- Mitigating context: the privileged jobs are guarded by `github.event.pull_request.user.login == 'renovate[bot]'` **and** `head.repo.full_name == github.repository`, so untrusted forks cannot reach the privileged path.
- **Decision required:**
  - [ ] Option 1 (accept): dismiss alert #1748 via `gh api repos/vig-os/devcontainer/code-scanning/alerts/1748 -X PATCH -f state=dismissed -f dismissed_reason="won't fix" -f dismissed_comment="<rationale>"`, documenting the guards.
  - [ ] Option 2 (refactor): split into a non-privileged `pull_request` job (build/upload artifact) + a privileged `workflow_run` job (commit), removing head checkout under `pull_request_target`.

### A2. CodeQL - actions/missing-workflow-permissions x4 (alerts #453-456) - STALE
- Files: `ci.yml`, `codeql.yml`, `scorecard.yml`, `security-scan.yml`.
- **Verified already remediated on `dev`:** all four declare explicit permissions (top-level + per-job). e.g. `ci.yml` top-level `contents: read`, `codeql.yml`/`scorecard.yml` `permissions: {}` + per-job scopes.
- **Action:** confirm the latest default-branch CodeQL run, then dismiss/let auto-resolve any that linger. Likely no code change needed.

### A3. Scorecard posture
- `BranchProtectionID` (high), `CodeReviewID` (high): governed by GitHub rulesets (SECURITY.md states protection via GitHub Enterprise). Verify rulesets require review.
- `VulnerabilitiesID` (high): roll-up of the Trivy/Dependabot vulns - auto-clears as buckets B-D land.
- `FuzzingID` (medium), `CIIBestPracticesID` (low): not meaningful for a devcontainer image repo - document as accepted/won't-fix.

### A4. Workspace template parity (downstream `vig-os/devcontainer-smoke-test`)

The smoke-test repo deploys copies of `assets/workspace/` templates. Equivalent Scorecard findings there are closely related to A1/A2 and should be fixed at the template source.

| Finding | Template file | Smoke-test impact |
| --- | --- | --- |
| `DangerousWorkflowID` (critical) | `assets/workspace/.github/workflows/renovate-changelog.yml` | Same `pull_request_target` + PR-head checkout pattern as A1 |
| `TokenPermissionsID` (high) on `release-extension.yml` | `assets/workspace/.github/workflows/release-extension.yml` | Only template workflow with **no** `permissions:` block |
| `TokenPermissionsID` x16 on other workflows | Already fixed in current templates | Stale deployed copies in smoke-test |

**Actions:**
- [ ] Apply the same A1 remediation to `assets/workspace/.github/workflows/renovate-changelog.yml` (accept+dismiss or refactor off `pull_request_target`).
- [ ] Add a `permissions:` block to `assets/workspace/.github/workflows/release-extension.yml`.
- [ ] **Also** apply the `release-extension.yml` permissions fix **directly in `vig-os/devcontainer-smoke-test`**, because that file is in `PRESERVE_FILES` in `assets/init-workspace.sh` (line 33) and is **never overwritten** by the release re-sync.
- [ ] The other ~16 `TokenPermissionsID` findings are stale copies; they clear automatically on the next release re-sync (no manual step). The `release.yml` smoke-test job dispatches `smoke-test-trigger`, which runs `init-workspace.sh --smoke-test` inside the newly released image.

### Acceptance criteria
- [ ] Alert #1748 resolved (dismissed-with-rationale or fixed by refactor)
- [ ] CodeQL alerts #453-456 closed/auto-resolved
- [ ] Branch-protection/code-review rulesets verified
- [ ] Fuzzing/CII findings documented as accepted
- [ ] Template `renovate-changelog.yml` and `release-extension.yml` fixed; smoke-test `release-extension.yml` patched directly

Refs: #512, #521
