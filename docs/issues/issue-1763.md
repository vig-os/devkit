---
type: issue
state: closed
created: 2026-09-29T11:15:41Z
updated: 2026-09-29T13:07:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1763
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch, security, dependencies
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:46.818Z
---

# [Issue 1763]: [fix(renovate): shipped Renovate config leaves smoke-test Python and Rust consumers without vulnerability-fix coverage](https://github.com/vig-os/devkit/issues/1763)

### Description

The org is moving vulnerability-fix PRs from Dependabot security updates to Renovate (vig-os/org-config#307). Renovate turns GitHub vulnerability alerts into forced packageRules at repo init, so vulnerability PRs follow `baseBranchPatterns`, bypass the schedule, carry a `[SECURITY]` suffix and inherit the preset's per-manager semantic commit types (which pass the managed commit gate).

A vulnerability rule only fires for dependencies an **enabled manager extracts**. The shipped Renovate config leaves gaps:

1. **Smoke-test has no Python coverage, and every deploy reverts a fix.** `assets/smoke-test/renovate.json:6` ships `"enabledManagers": ["github-actions"]`. Smoke mode copies the smoke overlay with no preserve excludes (`assets/init-workspace.sh:3338-3364`), so each deploy resets the smoke repo's `renovate.json`. This already reverted devkit-smoke-test#221 (smoke commit 2c99772, reverted by deploy 16f26dd). The smoke repo has `pyproject.toml` + `uv.lock` and no `package.json`, so it needs `["github-actions", "pep621"]`.
2. **Rust consumers get no Cargo coverage.** `assets/workspace/renovate.json:6` enables `github-actions, pep621, npm` only, no `cargo`. `renovate.json` is a `PRESERVE_FILES` entry (`assets/init-workspace.sh:141`), so existing consumers must hand-edit it.
3. **The preset has no Cargo rule and no explicit vulnerability-alert config.** `assets/workspace/.github/renovate-default.json` has no `cargo` packageRule (so a Cargo PR would not get an approved semantic type) and relies on the implicit `vulnerabilityAlerts` default.

### Steps to Reproduce

1. Scaffold a smoke-test deploy (`init-workspace.sh --smoke-test`) into a repo with `pyproject.toml` and read the rendered `renovate.json`.
2. Scaffold a Rust consumer and read the rendered `renovate.json`.
3. Read `assets/workspace/.github/renovate-default.json` `packageRules`.

### Expected Behavior

- Smoke-test `enabledManagers` includes `github-actions` and `pep621`, and survives every deploy.
- The workspace template enables `cargo` (a manager with nothing to extract is a no-op).
- The preset carries a `cargo` packageRule with an approved semantic type (before the managed-exclusion rule, which stays last) and an explicit `vulnerabilityAlerts` block labelled `security`.

### Actual Behavior

- Smoke-test: `["github-actions"]` only; deploys revert manual fixes.
- Workspace template: no `cargo`.
- Preset: no `cargo` rule, no explicit `vulnerabilityAlerts`.

### Environment

- **Image Version/Tag**: `dev` (post-1.17.0)
- Affects the shipped scaffold (`assets/workspace/`, `assets/smoke-test/`), not a runtime environment.

### Additional Context

- vig-os/org-config#307 (Dependabot security updates -> Renovate)
- #1041 (transitive dependencies rely on `lockFileMaintenance`)
- #1755

### Possible Solution

- `assets/smoke-test/renovate.json`: `"enabledManagers": ["github-actions", "pep621"]`.
- `assets/workspace/renovate.json`: add `cargo`.
- Preset: add `{"description": "Rust (Cargo)", "matchManagers": ["cargo"], "semanticCommitType": "build", "semanticCommitScope": "cargo"}` before the managed-exclusion rule; add `vulnerabilityAlerts` (`labels: ["security"]`) after `lockFileMaintenance`. No `osvVulnerabilityAlerts`.
- Docs: vulnerability-fix section in `docs/WORKFLOW_SECURITY.md`; `docs/MIGRATION.md` note for Rust consumers to add `cargo` to their preserved `renovate.json`.

**Acceptance criteria**

- [ ] Preset has `vulnerabilityAlerts` (not `enabled: false`) and no `osvVulnerabilityAlerts`
- [ ] Smoke `enabledManagers` ⊇ {`github-actions`, `pep621`}
- [ ] Workspace template `enabledManagers` includes `cargo`
- [ ] Every template-enabled manager has a preset packageRule whose `semanticCommitType` is in vig-utils' approved types (test-enforced)
- [ ] Managed-exclusion rule stays last (existing test green)
- [ ] `renovate-config-validator --strict` passes
- [ ] WORKFLOW_SECURITY.md + MIGRATION.md + CHANGELOG updated

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 29, 2026 at 01:07 PM_

Fixed on dev by #1764; ships with the next release.

