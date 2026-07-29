---
type: issue
state: open
created: 2026-07-28T13:27:00Z
updated: 2026-07-28T13:27:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1283
comments: 0
labels: feature, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:55.542Z
---

# [Issue 1283]: [feat(init): preflight failure for non-main default branches (legacy master lockout)](https://github.com/vig-os/devkit/issues/1283)

### Description

An installer/`init-workspace.sh` preflight check that detects a repo whose default branch is not `main` (legacy `master` being the common case) and fails loudly with rename instructions **before** writing anything.

### Problem Statement

The scaffolded branch-name enforcer (`no-commit-to-branch` regex in `.pre-commit-config.yaml`) permits only `main`, `dev`, and convention-named branches. On a legacy `master` repo the scaffold succeeds silently — and then **every subsequent commit is blocked** by a confusing hook error, because `master` matches none of the allowed patterns. `ci.yml`'s `TRUNK` retarget sed and the workflow triggers likewise assume `main`. The failure is invisible at scaffold time and lands at the worst moment (first commit after adoption).

### Proposed Solution

- Preflight in `init-workspace.sh` (and mirrored in `install.sh`): resolve the default branch (`git symbolic-ref refs/remotes/origin/HEAD` / `gh api ... --jq .default_branch`, with a local-only fallback); if it is not `main` (or `dev`+`main` for gitflow), abort with explicit guidance:
  - `git branch -m master main && git push -u origin main`
  - `gh repo edit --default-branch main`
- A short `docs/MIGRATION.md` section for legacy-`master` consumers.
- `--preview` should surface the same finding without aborting.

#### Acceptance criteria

- [ ] Scaffold on a `master`-default repo aborts pre-copy with actionable instructions
- [ ] Conforming repos see no behavior change
- [ ] bats coverage for the abort path

### Alternatives Considered

- **Full `{{TRUNK_BRANCH}}` tokenization** of the regex, the `ci.yml` sed, and workflow triggers, so any trunk name works. Deliberately out of scope here — renaming to `main` is a two-command fix for consumers, and tokenizing every branch reference is a much larger, riskier change. Noted as a possible follow-up if a consumer genuinely cannot rename.

### Additional Context

Surfaced while dry-running devkit adoption on a legacy repo still on `master`. Related: #1205 (workflow-model knob — same "consumer repo shape" preflight territory).

### Impact

- Prevents a silent-lockout footgun for every legacy adopter.
- No change for conforming repos; `semver:patch`.

