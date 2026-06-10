---
type: issue
state: closed
created: 2026-06-09T08:38:29Z
updated: 2026-06-09T21:28:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/568
comments: 0
labels: priority:medium, area:workflow, effort:medium, security
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:22.347Z
---

# [Issue 568]: [security(workspace): close downstream Scorecard gaps not covered by #562/#563 (SECURITY.md template, dispatch pinning, repo protections)](https://github.com/vig-os/devcontainer/issues/568)

## Downstream-only security findings (`vig-os/devcontainer-smoke-test`)

These smoke-test Security-tab alerts have **no upstream analog** in issues #562/#563. Fix at the template/overlay source where possible; apply one-time actions where auto-propagation does not apply.

### Propagation model

Most template fixes auto-land in the smoke-test repo on the next release:
1. `release.yml` smoke-test job dispatches `smoke-test-trigger` to `vig-os/devcontainer-smoke-test`
2. `assets/smoke-test/.github/workflows/repository-dispatch.yml` runs `init-workspace.sh --smoke-test` inside the newly released image
3. Clean `rsync --delete` of `assets/workspace/` + `assets/smoke-test/` overlay, then `just sync` regenerates `uv.lock`

**Exceptions (require one-time direct action on smoke-test repo):**
- `release-extension.yml` is in `PRESERVE_FILES` (`assets/init-workspace.sh` line 33) and is never overwritten on re-sync -> permissions fix tracked in #562 must also be applied directly in smoke-test
- `BranchProtectionID`, `CodeReviewID` are GitHub repo settings, not files -> configure on smoke-test repo

### Findings and actions

| Finding | Severity | Source | Action |
| --- | --- | --- | --- |
| `SecurityPolicyID` | medium | No `SECURITY.md` in `assets/workspace/` | Add template `SECURITY.md` (auto-propagates via re-sync) |
| `PinnedDependenciesID` | medium | `assets/smoke-test/.github/workflows/repository-dispatch.yml` | Pin actions/deps in the smoke-test overlay (auto-propagates via overlay rsync) |
| `BranchProtectionID` | high | Smoke-test repo settings | Configure rulesets requiring review |
| `CodeReviewID` | high | Smoke-test repo settings | Configure rulesets requiring review |
| `FuzzingID` | medium | Scorecard posture | Document as accepted/won't-fix for a test repo (mirrors #562 A3) |
| `CIIBestPracticesID` | low | Scorecard posture | Document as accepted/won't-fix for a test repo (mirrors #562 A3) |

### Acceptance criteria
- [ ] `SECURITY.md` added to `assets/workspace/` template
- [ ] `repository-dispatch.yml` actions pinned in `assets/smoke-test/` overlay
- [ ] Branch-protection and code-review rulesets configured on `vig-os/devcontainer-smoke-test`
- [ ] `release-extension.yml` permissions fixed directly in smoke-test (see #562 A4)
- [ ] Fuzzing/CII findings documented as accepted

### Related issues
- #562 - workflow template parity (renovate-changelog, release-extension permissions)
- #563 - Python dependency template source (jupyter stack, urllib3/idna)

Refs: #512, #521
