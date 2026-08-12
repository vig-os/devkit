---
type: issue
state: closed
created: 2026-08-12T05:14:56Z
updated: 2026-08-12T07:07:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1432
comments: 2
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:42.915Z
---

# [Issue 1432]: [[FEATURE] feat(workspace): scaffold-time branch-types knob (DEVKIT_BRANCH_TYPES) for the branch guard + mkProjectShell branchTypes](https://github.com/vig-os/devkit/issues/1432)

### Description

A `.vig-os` manifest key `DEVKIT_BRANCH_TYPES` that steers the issue-numbered alternation of the `no-commit-to-branch` branch guard — `(feature|bugfix|hotfix|release|docs|test|refactor)/<issue>-<slug>` — on **both** enforcement surfaces: the scaffolded `.pre-commit-config.yaml` (docker-mode consumers) and the flake-generated consumer config (direnv consumers, via a new `mkProjectShell` `branchTypes` argument). Twin of #1431; the branch-side half of exo-pet/vault#54 option B.

### Problem Statement

ADR-0002 in exo-pet/vault prescribes `record/<issue>-<summary>` branches, which the guard's fixed alternation rejects. The only routes today are hand-writing the full pattern regex into the consumer's `flake.nix` (`hooks."no-commit-to-branch".settings.pattern`) — which duplicates the whole regex and silently drifts from upstream pattern changes (e.g. the #1224 workflow-model clause) — or editing the preserved YAML (permanent drift nag).

### Proposed Solution

- New `.vig-os` key `DEVKIT_BRANCH_TYPES`: comma-separated full replacement of the issue-numbered type set; empty (default) = `feature,bugfix,hotfix,release,docs,test,refactor` — byte-identical default renders. The `chore/<slug>` and `worktree/<n>` clauses are untouched.
- `nix/hooks.nix`: `branchNamePatternFor` gains a branch-types parameter (alternation built from the list); default preserved exactly.
- `flake.nix` `mkProjectShell`: new `branchTypes ? null` argument (null = default set), validated at eval time with a loud throw on bad charset (mirrors the `workflow` guard), threaded into `hooksModule.consumer`.
- Template `flake.nix`: extend the existing `.vig-os` reader (#1224 pattern) to read `DEVKIT_BRANCH_TYPES` and forward it under a `functionArgs` guard. `flake.nix` is scaffold-once, so **existing direnv consumers hand-port the reader block** — documented in `docs/MIGRATION.md` like the workflow-model port.
- `init-workspace.sh`: read + charset guard + anchored render + conditional write-back; a notice (not abort) when `release` is dropped (the release train forks `release/X.Y.Z` branches).
- Docs: `docs/MIGRATION.md` manifest table; `branch-naming` skill (both copies).
- No CI branch-name gate exists — the two local surfaces are the whole story.

Spike evidence (2026-08-11, dev @4822b706): extended-alternation regex semantics proven (`record/54-x` allowed, `record/no-issue` still blocked, main/dev/chore/worktree clauses intact); anchored BRE sed with `#` delimiter proven against the template YAML (alternation occurs exactly once; composes with the trunk + refs-policy seds); the consumer-fragment `settings.pattern` override was built end-to-end and wins over the base (mkOverride 999), confirming the plumbing the new argument automates.

#### Acceptance criteria

- [ ] Default (absent/empty key) keeps both rendered patterns byte-identical (parity incl. `hooksPortable` drift gate)
- [ ] `branchTypes` composes with `workflow = "trunk"` (#1224) — both clauses render together
- [ ] Invalid charset refused loudly at scaffold time (bash) and eval time (nix)
- [ ] Round-trip across `--force` proven in bats; consumer-surface coverage in test_flake_hooks.py mirroring TestWorkflowModelBranchGuard

### Alternatives Considered

- **Consumer overrides `settings.pattern` with the full regex** — works today (spike-proven, usable as vault's interim unblock) but copies the whole pattern out of the SSoT.
- **Add `record` to the default alternation** — option A of exo-pet/vault#54, rejected for per-consumer flexibility.

### Additional Context

exo-pet/vault#54 (origin), #1431 (commit-types twin), #1224 (workflow-aware guard — the threading model), #1282 (knob blueprint).

### Impact

Backward compatible (semver:minor labeled; 1.7.1 train inclusion). Benefits any consumer with a domain-specific branching vocabulary.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 06:18 AM_

Scope extension (maintainer decision, from #1430 triage): this issue additionally ships the **CI branch-name gate** — a commit-checks step validating the PR head ref against the same resolved branch-types set, via a new `branch-types` resolve-toolchain output. Superset allowances for automation branches that never run local hooks (`release/X.Y.Z`, `renovate/*` per #1433, `worktree/<n>`, plus the scaffold-automation inventory), env-routed head ref, and the same step mirrored into devkit's own bespoke `ci.yml`. Rationale and acceptance mapping: https://github.com/vig-os/devkit/issues/1430#issuecomment-5263090624

Refs: #1430

---

# [Comment #2]() by [c-vigo]()

_Posted on August 12, 2026 at 07:07 AM_

Merged to dev via #1437 (dev-targeted PRs do not auto-close), including the #1430 CI branch-name gate. Ships with 1.7.1. Pre-train prerequisite: devkit-smoke-test#354 (dot-free deploy branch) must be on smoke main before the candidate dispatch.

