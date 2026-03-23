# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - TBD

### Added

- **Split downstream release workflow with project-owned extension hook** ([#326](https://github.com/vig-os/devcontainer/issues/326))
  - Add local `workflow_call` release phases (`release-core.yml`, `release-publish.yml`) and a lightweight `release.yml` orchestrator in `assets/workspace/.github/workflows/`
  - Add `release_kind` support with candidate mode (`X.Y.Z-rcN`) and final mode (`X.Y.Z`) in downstream release workflows
  - Candidate mode now auto-computes the next RC tag, skips CHANGELOG finalization/sync-issues, and publishes a GitHub pre-release
  - Add project-owned `release-extension.yml` stub and preserve it during `init-workspace.sh --force` upgrades
  - Add `validate-contract` composite action for single-source contract version validation
  - Add downstream release contract documentation and GHCR extension example in `docs/DOWNSTREAM_RELEASE.md`

### Changed

- **Dependabot dependency update batch** ([#302](https://github.com/vig-os/devcontainer/pull/302), [#303](https://github.com/vig-os/devcontainer/pull/303), [#305](https://github.com/vig-os/devcontainer/pull/305), [#306](https://github.com/vig-os/devcontainer/pull/306), [#307](https://github.com/vig-os/devcontainer/pull/307), [#308](https://github.com/vig-os/devcontainer/pull/308), [#309](https://github.com/vig-os/devcontainer/pull/309))
  - Bump `@devcontainers/cli` from `0.81.1` to `0.84.0` and `bats-assert` from `v2.2.0` to `v2.2.4`
  - Bump GitHub Actions: `actions/download-artifact` (`4.3.0` -> `8.0.1`), `actions/github-script` (`7.1.0` -> `8.0.0`), `actions/attest-build-provenance` (`3.0.0` -> `4.1.0`), `actions/checkout` (`4.3.1` -> `6.0.2`)
  - Bump release workflow action pins: `sigstore/cosign-installer` (`4.0.0` -> `4.1.0`) and `anchore/sbom-action` (`0.22.2` -> `0.23.1`)
- **Dependabot dependency update batch** ([#314](https://github.com/vig-os/devcontainer/pull/314), [#315](https://github.com/vig-os/devcontainer/pull/315), [#316](https://github.com/vig-os/devcontainer/pull/316), [#317](https://github.com/vig-os/devcontainer/pull/317))
  - Bump GitHub Actions: `actions/attest-sbom` (`3.0.0` -> `4.0.0`), `actions/upload-artifact` (`4.6.2` -> `7.0.0`), `actions/create-github-app-token` (`2.2.1` -> `3.0.0`)
  - Bump `docker/login-action` from `3.7.0` to `4.0.0`
  - Bump `just` minor version from `1.46` to `1.47`
- **Node24-ready GitHub Actions pin refresh for shared composite actions** ([#321](https://github.com/vig-os/devcontainer/issues/321))
  - Update Docker build path pins in `build-image` (`docker/setup-buildx-action`, `docker/metadata-action`, `docker/build-push-action`) to Node24-compatible releases
  - Set `setup-env` default Node runtime to `24` and upgrade `actions/setup-node`
  - Align test composite actions with newer pins (`actions/checkout`, `actions/cache`, `actions/upload-artifact`)
- **Smoke-test dispatch payload now carries source run traceability metadata** ([#289](https://github.com/vig-os/devcontainer/issues/289))
  - Candidate release dispatches now include source repo/workflow/run/SHA metadata plus a deterministic `correlation_id`
  - Smoke-test dispatch receiver logs normalized source context, derives source run URL when possible, and writes it to workflow summary output
  - Release-cycle docs now define required vs optional dispatch payload keys and the future callback contract path for `publish-candidate`
- **Smoke-test repository dispatch now runs for final releases too** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - `release.yml` now triggers the existing smoke-test dispatch contract for both `candidate` and `final` release kinds
  - Final release summaries and release-cycle documentation now reflect dispatch behavior for both release modes
- **Workspace CI templates now use a single container-based workflow** ([#327](https://github.com/vig-os/devcontainer/issues/327))
  - Consolidate `assets/workspace/.github/workflows/ci.yml` as the canonical CI workflow and remove the obsolete `ci-container.yml` template
  - Extract reusable `assets/workspace/.github/actions/resolve-image` and run workspace release tests in the same containerized workflow model
  - Update smoke-test and release-cycle documentation to reference the single CI workflow contract
- **Final release now requires downstream RC pre-release gate** ([#331](https://github.com/vig-os/devcontainer/issues/331))
  - Add upstream final-release validation that requires a downstream GitHub pre-release for the latest published RC tag
  - Move smoke-test dispatch to a dedicated release job and include `release_kind` in the dispatch payload
  - Add downstream `repository-dispatch.yml` template that runs smoke tests and creates pre-release/final release artifacts
- **Ship changelog into workspace payload and smoke-test deploy root** ([#333](https://github.com/vig-os/devcontainer/issues/333))
  - Sync canonical `CHANGELOG.md` into both workspace root and `.devcontainer/` template paths
  - Smoke-test dispatch now copies `.devcontainer/CHANGELOG.md` to repository root so deploy output keeps a root changelog
- **Final release now publishes a GitHub Release with finalized notes** ([#310](https://github.com/vig-os/devcontainer/issues/310))
  - Add a final-only publish step in `.github/workflows/release.yml` that creates a GitHub Release for `X.Y.Z`
  - Source GitHub Release notes from the finalized `CHANGELOG.md` section and fail the run if notes extraction or release publishing fails
- **Release dispatch and publish ordering hardened for 0.3.1** ([#336](https://github.com/vig-os/devcontainer/issues/336))
  - Make smoke-test dispatch fire-and-forget in `.github/workflows/release.yml` and decouple rollback from downstream completion timing
  - Add bounded retries to the final-release downstream RC pre-release gate API check
  - Move final GitHub Release creation to the end of publish so artifact publication/signing completes before release object creation
  - Add concurrency control to `assets/smoke-test/.github/workflows/repository-dispatch.yml` to prevent overlapping dispatch races
  - Handle smoke-test dispatch failures with a targeted issue while avoiding destructive rollback after publish artifacts are already released
- **Redesigned smoke-test dispatch release orchestration** ([#358](https://github.com/vig-os/devcontainer/issues/358))
  - Replace premature `publish-release` behavior with full downstream orchestration: deploy-to-dev merge gate, `prepare-release.yml`, release PR readiness/approval, and `release.yml` dispatch polling
  - Add upstream failure issue reporting with job-phase results and cleanup guidance when dispatch orchestration fails
- **Smoke-test release orchestration now runs as two phases** ([#402](https://github.com/vig-os/devcontainer/issues/402))
  - Keep `repository-dispatch.yml` focused on deploy/prepare/release-PR readiness and move release dispatch to a dedicated merged-PR workflow (`on-release-pr-merge.yml`)
  - Add release-kind labeling and auto-merge enablement for release PRs, and keep upstream failure notifications in both phases
  - Remove release-branch upstream `CHANGELOG.md` sync from `repository-dispatch.yml` (previously added in [#358](https://github.com/vig-os/devcontainer/issues/358))
- **Dependabot dependency update batch** ([#414](https://github.com/vig-os/devcontainer/pull/414))
  - Bump `github/codeql-action` from `4.32.6` to `4.34.1` and `anchore/sbom-action` from `0.23.1` to `0.24.0`
  - Bump `actions/cache` restore/save pins from `5.0.3` to `5.0.4` in `sync-issues.yml`
- **Dependabot dependency update batch** ([#413](https://github.com/vig-os/devcontainer/pull/413))
  - Bump `@devcontainers/cli` from `0.84.0` to `0.84.1`

### Fixed

- **Smoke-test deploy restores workspace CHANGELOG for prepare-release** ([#417](https://github.com/vig-os/devcontainer/issues/417))
  - Add `prepare-changelog unprepare` to rename the top `## [semver] - …` heading to `## Unreleased`
  - `init-workspace.sh --smoke-test` copies `.devcontainer/CHANGELOG.md` into workspace `CHANGELOG.md` and runs unprepare; remove duplicate remap from smoke-test dispatch workflow
- **Release app permission docs now include downstream workflow dispatch requirements** ([#397](https://github.com/vig-os/devcontainer/issues/397))
  - Update `docs/RELEASE_CYCLE.md` to require `Actions` read/write for `RELEASE_APP` on the validation repository
  - Clarify this is required so downstream `repository-dispatch.yml` can trigger release orchestration workflows via `workflow_dispatch`
- **Smoke-test dispatch no longer fails on release PR self-approval** ([#402](https://github.com/vig-os/devcontainer/issues/402))
  - Remove bot self-approval from `repository-dispatch.yml` and replace with release-kind labeling plus auto-merge enablement
  - Remove in-job polling for release PR merge and downstream release execution from phase 1 orchestration
  - Phase 2 (`on-release-pr-merge.yml`) fails validation unless the merged release PR has `release-kind:final` or `release-kind:candidate`
- **Sync-main-to-dev PRs now trigger CI reliably in downstream repos** ([#398](https://github.com/vig-os/devcontainer/issues/398))
  - Replace API-based sync branch creation with `git push` in `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- **Sync-main-to-dev no longer dispatches CI via workflow_dispatch** ([#405](https://github.com/vig-os/devcontainer/issues/405))
  - `workflow_dispatch` runs are omitted from the PR status check rollup, so they do not satisfy branch protection on the sync PR
  - Remove the post-PR `gh workflow run ci.yml` step and drop `actions: write` from the sync job in `.github/workflows/sync-main-to-dev.yml` and `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- **Sync-main-to-dev conflict detection uses merge-tree** ([#410](https://github.com/vig-os/devcontainer/issues/410))
  - Replace working-tree trial merge with `git merge-tree --write-tree` so clean merges are not mislabeled as conflicts
  - Enable auto-merge when dev merges cleanly with main; print merge-tree output on conflicts; fail the step on unexpected errors
- **Smoke-test release phase 2 branch-not-found failure** ([#419](https://github.com/vig-os/devcontainer/issues/419))
  - Merge phase 2 (`on-release-pr-merge.yml`) back into `repository-dispatch.yml` so the release runs while `release/<version>` still exists, matching the normal release flow
  - Remove `on-release-pr-merge.yml` from the smoke-test template

- **Release finalization now commits generated docs and refreshes PR content** ([#300](https://github.com/vig-os/devcontainer/issues/300))
  - Final release automation regenerates docs before committing so pre-commit `generate-docs` does not fail CI with tracked file diffs
  - Release PR body is refreshed from finalized `CHANGELOG.md`
- **Release attestation warnings reduced by granting artifact metadata permission** ([#348](https://github.com/vig-os/devcontainer/issues/348))
  - Add `artifact-metadata: write` to the release publish job so attestation steps can persist metadata storage records
  - Keep `actions/attest`-based SBOM attestation path and remove missing-permission warnings from publish runs
- **Smoke-test dispatch deploy now repairs workspace ownership before changelog copy** ([#352](https://github.com/vig-os/devcontainer/issues/352))
  - Add a write probe and conditional `sudo chown -R` in `assets/smoke-test/.github/workflows/repository-dispatch.yml` after installer execution
  - Prevent `Permission denied` failures when copying `.devcontainer/CHANGELOG.md` to repository root in GitHub-hosted runner jobs
- **Smoke-test release lookup no longer treats missing tags as existing releases** ([#355](https://github.com/vig-os/devcontainer/issues/355))
  - Change `assets/smoke-test/.github/workflows/repository-dispatch.yml` to branch on `gh api` exit status when querying `releases/tags/<tag>`
  - Ensure missing release tags follow the create path instead of failing with `prerelease=null` mismatch
- **Bounded retry added for network-dependent setup and prepare-release calls** ([#357](https://github.com/vig-os/devcontainer/issues/357))
  - Replace shell-based retry helper with pure Python `retry` CLI in `vig-utils` (`packages/vig-utils/src/vig_utils/retry.py`)
  - Update this repository CI workflows to call `uv run retry` after `setup-env` dependency sync
  - Update downstream workflow templates to call `retry` directly in devcontainer jobs and remove `source` lines
  - Ensure downstream containerized jobs resolve image tags from `.vig-os` instead of hardcoded `latest`
  - Bundle idempotency guards for branch/PR/tag/release creation paths to keep retried network calls safe on reruns
  - Remove synced `retry.sh` artifacts and BATS retry tests in favor of `vig-utils` pytest coverage
- **Release workflow no longer fails when retry tooling is unavailable** ([#365](https://github.com/vig-os/devcontainer/issues/365))
  - Extend `.github/actions/setup-env/action.yml` with a reusable `retry` shell function exported via `BASH_ENV` as the retry single source of truth
  - Add `setup-env` input support for uv-only usage by allowing Python setup to be disabled when jobs only need retry tooling
  - Switch release workflow retry calls from `uv run retry` to shared `retry` and remove duplicated inline retry implementations
- **Upstream sync workflows no longer depend on pre-published GHCR image tags** ([#367](https://github.com/vig-os/devcontainer/issues/367))
  - Remove upstream `.vig-os` files at repository root and `assets/smoke-test/` to eliminate downstream-only configuration from upstream CI
  - Refactor `.github/workflows/sync-issues.yml` and `.github/workflows/sync-main-to-dev.yml` to run natively on runners via `./.github/actions/setup-env` instead of `resolve-image` + `container`
- **Release test-image setup now recovers from uv sync crashes** ([#370](https://github.com/vig-os/devcontainer/issues/370))
  - Harden `.github/actions/setup-env/action.yml` to retry `uv sync --frozen --all-extras` once after clearing uv cache and removing stale `.venv`
  - Prevent repeat release test failures when `setup-env` is executed multiple times in the same job
- **Release setup-env no longer self-sources retry helper via BASH_ENV** ([#374](https://github.com/vig-os/devcontainer/issues/374))
  - Guard the retry-helper merge logic in `.github/actions/setup-env/action.yml` to skip merging when `PREV_BASH_ENV` already equals `RETRY_HELPER`
  - Prevent infinite `source` recursion and exit 139 crashes when `setup-env` is invoked multiple times in one job
- **Smoke-test dispatch now checks out repository before local setup action** ([#376](https://github.com/vig-os/devcontainer/issues/376))
  - Add `actions/checkout` to the `smoke-test` job in `.github/workflows/release.yml` before invoking `./.github/actions/setup-env`
  - Prevent dispatch failures caused by missing local action metadata (`action.yml`) in a fresh job workspace
- **Workspace resolve-image jobs now checkout local action metadata** ([#380](https://github.com/vig-os/devcontainer/issues/380))
  - Update `sparse-checkout` in workspace `resolve-image` jobs to include `.github/actions/resolve-image` in addition to `.vig-os`
  - Prevent CI failures in downstream deploy PRs where local composite actions were missing from sparse checkout
- **Smoke-test dispatch gh jobs now set explicit repo context** ([#386](https://github.com/vig-os/devcontainer/issues/386))
  - Add job-level `GH_REPO: ${{ github.repository }}` to `cleanup-release`, `trigger-prepare-release`, `ready-release-pr`, and `trigger-release` in `assets/smoke-test/.github/workflows/repository-dispatch.yml`
  - Prevent `gh` CLI failures (`fatal: not a git repository`) in runner jobs that do not perform `actions/checkout`
- **Smoke-test release orchestration now validates workflow contract before dispatch** ([#389](https://github.com/vig-os/devcontainer/issues/389))
  - Add a preflight check that verifies `prepare-release.yml` and `release.yml` are resolvable on dispatch ref `dev` before downstream orchestration starts
  - Dispatch and polling now use explicit ref/branch context (`--ref dev` / `--branch dev`) to avoid default-branch workflow registry drift and `404 workflow not found` failures
- **Smoke-test preflight now uses gh CLI ref-compatible workflow validation** ([#392](https://github.com/vig-os/devcontainer/issues/392))
  - Update `assets/smoke-test/.github/workflows/repository-dispatch.yml` preflight checks to call `gh workflow view` with `--yaml` when `--ref` is set
  - Prevent false preflight failures caused by newer GitHub CLI argument validation before `prepare-release` dispatch
- **Downstream release workflow templates hardened for smoke-test orchestration** ([#394](https://github.com/vig-os/devcontainer/issues/394))
  - Add missing `git config --global --add safe.directory "$GITHUB_WORKSPACE"` in containerized release and sync jobs that run git after checkout
  - Decouple `release.yml` rollback container startup from `needs.core.outputs.image_tag` by resolving the image in a dedicated `resolve-image` job
  - Add explicit release caller/reusable workflow permissions for `actions` and `pull-requests` operations, and update dispatch header comments to reference only current CI workflows
- **Workspace containerized workflows now pin bash for run steps** ([#395](https://github.com/vig-os/devcontainer/issues/395))
  - Set `defaults.run.shell: bash` in containerized workspace release and prepare jobs so `set -euo pipefail` scripts do not execute under POSIX `sh`
  - Prevent downstream smoke-test failures caused by `set: Illegal option -o pipefail` in container jobs
- **Downstream release templates now require explicit app tokens for write paths** ([#400](https://github.com/vig-os/devcontainer/issues/400))
  - Update `assets/workspace/.github/workflows/prepare-release.yml`, `release-core.yml`, `release-publish.yml`, `release.yml`, and `sync-issues.yml` to remove `github.token` fallback from protected write operations
  - Route protected branch/ref writes through Commit App tokens and release orchestration/issue operations through Release App tokens
  - Document downstream token requirements in `docs/DOWNSTREAM_RELEASE.md` and `docs/CROSS_REPO_RELEASE_GATE.md`
  - Use `github.token` specifically for Actions cache deletion in `sync-issues.yml` because that API path requires explicit `actions: write` job token scope
  - Use Commit App credentials for rollback checkout in `release.yml` so rollback branch/tag writes can still bypass protected refs
- **setup-env retries uv install on transient GitHub Releases download failures** ([#407](https://github.com/vig-os/devcontainer/issues/407))
  - Add `continue-on-error` plus a delayed second attempt for `astral-sh/setup-uv` in `.github/actions/setup-env/action.yml`
  - Reduce flaky release publish failures when GitHub CDN returns transient HTTP errors for uv release assets
- **Smoke-test deploy keeps workspace scaffold as root CHANGELOG** ([#403](https://github.com/vig-os/devcontainer/issues/403))
  - Stop overwriting `CHANGELOG.md` with a minimal stub in `assets/smoke-test/.github/workflows/repository-dispatch.yml`
  - Require the workspace `CHANGELOG.md` from `init-workspace` so downstream `prepare-release` validation matches shipped layout
  - When the first changelog section is `## [X.Y.Z] - …` (TBD or a release date), remap that top version header to `## Unreleased` so downstream `prepare-release` can run

### Security

- **Smoke-test dispatch workflow permissions now follow least privilege** ([#340](https://github.com/vig-os/devcontainer/issues/340))
  - Reduce `assets/smoke-test/.github/workflows/repository-dispatch.yml` workflow token permissions from write to read by default
  - Grant `contents: write` only to `publish-release`, the single job that creates or edits GitHub Releases

## [0.3.0](https://github.com/vig-os/devcontainer/releases/tag/0.3.0) - 2026-03-13

### Added

- **Image tools** ([#212](https://github.com/vig-os/devcontainer/issues/212))
  - Install rsync
- **Preserve user-authored files during `--force` workspace upgrades** ([#212](https://github.com/vig-os/devcontainer/issues/212))
  - `init-workspace --force` no longer overwrites `README.md`, `CHANGELOG.md`, `LICENSE`, `.github/CODEOWNERS`, or `justfile.project`
- **Devcontainer and git recipes in justfile.base** ([#71](https://github.com/vig-os/devcontainer/issues/71))
  - Devcontainer group (host-side only): `up`, `down`, `status`, `logs`, `shell`, `restart`, `open`
  - Auto-detect podman/docker compose; graceful failure if run inside container
  - Git group: `log` (pretty one-line, last 20), `branch` (current + recent)
- **CI status column in just gh-issues PR table** ([#143](https://github.com/vig-os/devcontainer/issues/143))
  - PR table shows CI column with pass/fail/pending summary (✓ 6/6, ⏳ 3/6, ✗ 5/6)
  - Failed check names visible when checks fail
  - CI cell links to GitHub PR checks page
- **Config-driven model tier assignments for agent skills** ([#103](https://github.com/vig-os/devcontainer/issues/103))
  - Extended `.cursor/agent-models.toml` with `standard` tier (sonnet-4.5) and `[skill-tiers]` mapping for skill categories (data-gathering, formatting, review, orchestration)
  - New rule `.cursor/rules/subagent-delegation.mdc` documenting when and how to delegate mechanical sub-steps to lightweight subagents via the Task tool
  - Added `## Delegation` sections to 12 skills identifying steps that should spawn lightweight/standard-tier subagents to reduce token consumption on the primary autonomous model
  - Skills updated: `worktree_solve-and-pr`, `worktree_brainstorm`, `worktree_plan`, `worktree_execute`, `worktree_verify`, `worktree_pr`, `worktree_ci-check`, `worktree_ci-fix`, `code_review`, `issue_triage`, `pr_post-merge`, `ci_check`
- **hadolint pre-commit hook for Containerfile linting** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Add `hadolint` hook to `.pre-commit-config.yaml`, pinned by SHA (v2.9.3)
  - Enforce Dockerfile best practices: pinned base image tags, consolidated `RUN` layers, shellcheck for inline scripts
  - Fix `tests/fixtures/sidecar.Containerfile` to pass hadolint with no warnings
- **tmux installed in container image for worktree session persistence** ([#130](https://github.com/vig-os/devcontainer/issues/130))
  - Add `tmux` to the Containerfile `apt-get install` block
  - Enables autonomous worktree agents to survive Cursor session disconnects
- **pr_solve skill — diagnose PR failures, plan fixes, execute** ([#133](https://github.com/vig-os/devcontainer/issues/133))
  - Single entry point that gathers CI failures, review feedback, and merge state into a consolidated diagnosis
  - Presents diagnosis for approval before any fixes, plans fixes using design_plan conventions, executes with TDD discipline
  - Pre-commit hook `check-skill-names` enforces `[a-z0-9][a-z0-9_-]*` naming for skill directories
  - BATS test suite with canary test that injects a bad name into the real repo
  - TDD scenario checklist expanded with canary, idempotency, and concurrency categories
- **Optional reviewer parameter for autonomous worktree pipeline** ([#102](https://github.com/vig-os/devcontainer/issues/102))
  - Support `reviewer` parameter in `just worktree-start`
  - Propagate `PR_REVIEWER` via tmux environment to the autonomous agent
  - Update `worktree_pr` skill to automatically request review when `PR_REVIEWER` is set
- **Inception skill family for pre-development product thinking** ([#90](https://github.com/vig-os/devcontainer/issues/90))
  - Four-phase pipeline: `inception_explore` (divergent problem understanding), `inception_scope` (convergent scoping), `inception_architect` (pattern-validated design), `inception_plan` (decomposition into GitHub issues)
  - Document templates: `docs/templates/RFC.md` (Problem Statement, Proposed Solution, Alternatives, Impact, Phasing) and `docs/templates/DESIGN.md` (Architecture, Components, Data Flow, Technology Stack, Testing)
  - Document directories: `docs/rfcs/` and `docs/designs/` for durable artifacts
  - Certified architecture reference repos embedded in `inception_architect` skill: ByteByteGoHq/system-design-101, donnemartin/system-design-primer, karanpratapsingh/system-design, binhnguyennus/awesome-scalability, mehdihadeli/awesome-software-architecture
  - Fills the gap between "I have an idea" and "I have issues ready for design"
- **Automatic update notifications on devcontainer attach** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Wire `version-check.sh` into `post-attach.sh` for automatic update checks
  - Silent, throttled checks (24-hour interval by default)
  - Graceful failure - never disrupts the attach process
- **Host-side devcontainer upgrade recipe** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - New `just devcontainer-upgrade` recipe for convenient upgrades from host
  - Container detection - prevents accidental execution inside devcontainer
  - Clear error messages with instructions when run from wrong context
- **`just check` recipe for version management** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Expose version-check.sh subcommands: `just check`, `just check config`, `just check on/off`, `just check 7d`
  - User-friendly interface for managing update notifications
- **Cursor worktree support for parallel agent development** ([#64](https://github.com/vig-os/devcontainer/issues/64))
  - `.cursor/worktrees.json` for native Cursor worktree initialization (macOS/Linux local)
  - `justfile.worktree` with tmux + cursor-agent CLI recipes (`worktree-start`, `worktree-list`, `worktree-attach`, `worktree-stop`, `worktree-clean`) for devcontainer environments
  - Autonomous worktree skills: `worktree_brainstorm`, `worktree_plan`, `worktree_execute`, `worktree_verify`, `worktree_pr`, `worktree_ask`, `worktree_solve-and-pr`
  - Sync manifest updated to propagate worktree config and recipes to downstream projects
- **GitHub issue and PR dashboard recipe** ([#84](https://github.com/vig-os/devcontainer/issues/84))
  - `just gh-issues` displays open issues grouped by milestone in rich tables with columns for type, title, assignee, linked branch, priority, scope, effort, and semver
  - Open pull requests section with author, branch, review status, and diff delta
  - Linked branches fetched via a single GraphQL call
  - Ships to downstream workspaces via sync manifest (`.devcontainer/justfile.gh` + `.devcontainer/scripts/gh_issues.py`)
- **Issue triage agent skill** ([#81](https://github.com/vig-os/devcontainer/issues/81))
  - Cursor skill at `.cursor/skills/issue_triage/` for triaging open issues across priority, area, effort, SemVer impact, dependencies, and release readiness
  - Decision matrix groups issues into parent/sub-issue clusters with milestone suggestions
  - Predefined label taxonomy (`label-taxonomy.md`) for priority, area, effort, and SemVer dimensions
  - Sync manifest updated to propagate skill to workspace template
- **Cursor commands and rules for agent-driven development workflows** ([#63](https://github.com/vig-os/devcontainer/issues/63))
  - Always-on rules: `coding-principles.mdc` (YAGNI, minimal diff, DRY, no secrets, traceability, single responsibility) and `tdd.mdc` (RED-GREEN-REFACTOR discipline)
  - Tier 1 commands: `start-issue.md`, `create-issue.md`, `brainstorm.md`, `tdd.md`, `review.md`, `verify.md`
  - Tier 2 commands: `check-ci.md`, `fix-ci.md`
  - Tier 3 commands: `plan.md`, `execute-plan.md`, `debug.md`
- **Agent-friendly issue templates, changelog rule, and PR template enhancements** ([#61](https://github.com/vig-os/devcontainer/issues/61))
  - Cursor rule `.cursor/rules/changelog.mdc` (always applied) guiding agents on when, where, and how to update CHANGELOG.md
  - Changelog Category dropdown added to `bug_report.yml`, `feature_request.yml`, and `task.yml` issue templates
  - New issue templates: `refactor.yml` (scope/invariants), `documentation.yml` (docs/templates workflow), `ci_build.yml` (target workflows/triggers/release impact)
  - Template chooser `config.yml` disabling blank issues and linking to project docs
  - PR template enhanced with explicit Changelog Entry section, CI/Build change type, and updated checklist referencing `docs/templates/` and `just docs`
- **GitHub issue and PR templates in workspace template** ([#63](https://github.com/vig-os/devcontainer/issues/63))
  - Pull request template, issue templates, Dependabot config, and `.gitmessage` synced to `assets/workspace/`
  - Ground truth lives in repo root; `assets/workspace/` is generated output
- **cursor-agent CLI pre-installed in devcontainer image** ([#108](https://github.com/vig-os/devcontainer/issues/108))
  - Enables `just worktree-start` to work out of the box without manual installation
- **Automatic merge commit message compliance** ([#79](https://github.com/vig-os/devcontainer/issues/79))
  - `setup-gh-repo.sh` configures repo merge settings via `gh api` (`merge_commit_title=PR_TITLE`, `merge_commit_message=PR_BODY`, `allow_auto_merge=true`)
  - Wired into `post-create.sh` so downstream devcontainer projects get compliant merge commits automatically
  - `--subject-only` flag for `validate-commit-msg` to validate PR titles without requiring body or Refs
  - `pr-title-check.yml` CI workflow enforces commit message standard on PR titles
  - PR body template includes `Refs: #` placeholder for merge commit traceability
- **Smoke-test repo bootstrap validation** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Downstream smoke coverage that bootstraps a workspace from the template and verifies `ci.yml` passes on a real GitHub-hosted runner
- **`bandit` pre-installed in devcontainer image** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - `bandit[toml]` added to the system Python install in the Containerfile
- **`pre-commit` pre-installed in CI `setup-env` action** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Workspace `setup-env` composite action now installs `pre-commit` as a mandatory step so hooks are available in bare-runner CI without a devcontainer
- **`setup-gh-repo.sh` detaches org default code security configuration** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - On post-create, detach any org-level default security config from the repo to avoid conflicts with the security workflows shipped in the workspace template
  - Graceful fallback when repo ID cannot be resolved or permissions are insufficient
- **`init-workspace.sh` runs `just sync` after placeholder replacement** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Resolves the `uv.lock` for the new project name and installs the project package into the venv during workspace bootstrap
- **Candidate publishing mode in release workflow** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `release.yml` now supports `release-kind=candidate` (default) and infers the next available `X.Y.Z-rcN` tag automatically
  - Candidate runs create and push Git tags, publish candidate manifests, and keep candidate tags after final release
  - Final runs remain available via `release-kind=final` and are exposed by `just finalize-release`
- **PR-based dev sync after release** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `sync-main-to-dev.yml` replaces `post-release.yml` — syncs main into dev via PR instead of direct push, satisfying branch protection rules
  - Detects merge conflicts, labels `merge-conflict` with resolution instructions
  - Auto-merge enabled for conflict-free PRs; stale sync branches cleaned up automatically
- **hadolint installed and wired into CI tooling** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Install `hadolint` in the devcontainer image with SHA-256 checksum verification
  - Add image test coverage to verify `hadolint` is available in the built image
  - Configure pre-commit to use the local `hadolint` binary and install it in `setup-env`/`test-project` workflows
- **Taplo TOML linting in pre-commit** ([#181](https://github.com/vig-os/devcontainer/issues/181))
  - Add SHA-pinned `taplo-format` and `taplo-lint` hooks to enforce TOML formatting and schema-aware validation
  - Add `.taplo.toml` configuration (local to this repository, not synced downstream)
- **Add `--smoke-test` flag to deploy smoke-test-specific assets** ([#250](https://github.com/vig-os/devcontainer/issues/250))
  - `init-workspace.sh --smoke-test` deploys files from `assets/smoke-test/` (currently `repository-dispatch.yml` and `README.md`)
  - `install.sh` forwards `--smoke-test` flag to `init-workspace.sh`
  - Smoke mode implies `--force --no-prompts` for unattended use
  - Refactor `initialized_workspace` fixture into reusable `_init_workspace()` with `smoke_test` parameter
- **Root `.vig-os` config file as devcontainer version SSoT** ([#257](https://github.com/vig-os/devcontainer/issues/257))
  - Add committed `assets/workspace/.vig-os` key/value config with `DEVCONTAINER_VERSION` as the canonical version source
  - Update `docker-compose.yml`, `initialize.sh`, and `version-check.sh` to consume `.vig-os`-driven version flow
  - Extend integration/image tests for `.vig-os` presence and graceful handling when `.vig-os` is missing
- **VS Code settings synced via manifest**
  - Added `.vscode/settings.json` to `scripts/manifest.toml` to keep editor settings consistent across root repo and workspace template
- **Cross-repo smoke-test dispatch on RC publish** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - RC candidate publishes now trigger `repository_dispatch` in `vig-os/devcontainer-smoke-test` with the RC tag payload
  - Release process now includes a documented manual smoke gate before running final publish
- **Automated RC deploy-and-test via PR in smoke-test repo** ([#258](https://github.com/vig-os/devcontainer/issues/258))
  - Dispatch workflow now deploys the tag, creates a signed commit on `chore/deploy-<tag>`, and opens a PR to `dev`
  - CI workflows (`ci.yml`, `ci-container.yml`) trigger on the deploy PR, and auto-merge is enabled when checks pass
  - Stale deploy PRs are closed before each new deployment
  - The smoke-test repo keeps audit trail through deploy PRs and merge history instead of a local changelog
  - Dispatch payload tag validation now enforces semver format `X.Y.Z` or `X.Y.Z-rcN` before using the tag in refs/URLs
  - CI security scan now includes a time-bounded exception for `CVE-2026-31812` in `uv`/`uvx` pending upstream dependency patch release

### Changed

- **Release CHANGELOG flow redesigned** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `prepare-release.yml` now freezes CHANGELOG on dev (Unreleased → [X.Y.Z] - TBD + fresh empty Unreleased), then forks release branch and strips the empty Unreleased section
  - Dev never enters a state without `## Unreleased`; both branches share the [X.Y.Z] section for clean merges
  - Candidate releases skip CHANGELOG changes; only final releases set the date
  - No CHANGELOG reset needed during post-release sync
- **Release automation now uses dedicated GitHub App identities** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - Replaced deprecated `APP_SYNC_ISSUES_*` secrets with `RELEASE_APP_*` for release and preparation workflows
  - `sync-issues.yml` now uses `COMMIT_APP_*`; `sync-main-to-dev.yml` uses both apps (commit app for refs, release app for PR operations)
  - Removed automatic `sync-issues` trigger from `sync-main-to-dev.yml` and documented the app permission model in `docs/RELEASE_CYCLE.md`
- **Container CI defaults image tag from `.vig-os`** ([#264](https://github.com/vig-os/devcontainer/issues/264))
  - `ci.yml` and `ci-container.yml` now run only on `pull_request` and `workflow_dispatch` after removing unused `workflow_call` triggers
  - `ci-container.yml` now resolves `DEVCONTAINER_VERSION` from `.vig-os` before container jobs start
  - Manual `workflow_dispatch` runs can still override the image via `image-tag`; fallback remains `latest` when no version is available
  - Added an early manifest check in `resolve-image` so workflows fail fast if the resolved image tag is unavailable or inaccessible

- **worktree-clean: add filter mode for stopped-only vs all** ([#158](https://github.com/vig-os/devcontainer/issues/158))
  - Default `just worktree-clean` (no args) now cleans only stopped worktrees, skips running tmux sessions
  - `just worktree-clean all` retains previous behavior (clean all worktrees) with warning
  - Summary output shows cleaned vs skipped worktrees
  - `just wt-clean` alias unchanged
- **Consolidate sync_manifest.py and utils.py into manifest-as-config architecture** ([#89](https://github.com/vig-os/devcontainer/issues/89))
  - Extract transform classes (Sed, RemoveLines, etc.) to `scripts/transforms.py`
  - Unify sed logic: `substitute_in_file()` in utils shared by sed_inplace and Sed transform
  - Convert MANIFEST from Python code to declarative `scripts/manifest.toml`
- **justfile.base is canonical at repo root, synced via manifest** ([#71](https://github.com/vig-os/devcontainer/issues/71))
  - Root `justfile.base` is now the single source of truth; synced to `assets/workspace/.devcontainer/justfile.base` via `sync_manifest.py`
  - `just sync-workspace` and prepare-build keep workspace template in sync
- **Autonomous PR skills use pull request template** ([#147](https://github.com/vig-os/devcontainer/issues/147))
  - `pr_create` and `worktree_pr` now read `.github/pull_request_template.md` and fill each section from available context
  - Explicit read-then-fill procedure with section-by-section mapping (Description, Type of Change, Changelog Entry, Testing, Checklist, Refs)
  - Ensures autonomous PRs match manual PR structure and include all checklist items
- **Rename skill namespace separator from colon to underscore** ([#128](https://github.com/vig-os/devcontainer/issues/128))
  - All skill directories under `.cursor/skills/` and `assets/workspace/.cursor/skills/` renamed (e.g. `issue:create` → `issue_create`)
  - All internal cross-references, frontmatter, prose, `CLAUDE.md` command table, and label taxonomy updated
  - `issue_create` skill enhanced: gathers context via `just gh-issues` before drafting, suggests parent/child relationships and milestones
  - `issue_create` skill now includes TDD acceptance criterion for testable issue types
  - Remaining `sync-issues` workflow trigger references removed from skills
  - `tdd.mdc` expanded with test scenario checklist and test type guidance; switched from always-on to glob-triggered on source/test files
  - `code_tdd`, `code_execute`, and `worktree_execute` skills now reference `tdd.mdc` explicitly
- **Clickable issue and PR numbers in gh-issues table** ([#104](https://github.com/vig-os/devcontainer/issues/104))
  - `#` column in issue and PR tables now uses Rich OSC 8 hyperlinks to GitHub URLs
  - Clicking an issue or PR number opens it in the browser (or Cursor's integrated terminal)
- **PR template aligned with canonical commit types** ([#115](https://github.com/vig-os/devcontainer/issues/115))
  - Replace ad-hoc Type of Change checkboxes with the 10 canonical commit types
  - Move breaking change from type to a separate modifier checkbox
  - Add release-branch hint to Related Issues section
- **Updated update notification message** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Fixed misleading `just update` instruction (Python deps, not devcontainer upgrade)
  - Show correct upgrade instructions: `just devcontainer-upgrade` and curl fallback
  - Clarify that upgrade must run from host terminal, not inside container
  - Add reminder to rebuild container in VS Code after upgrade
- **Declarative Python sync manifest** ([#67](https://github.com/vig-os/devcontainer/issues/67))
  - Replaced `sync-manifest.txt` + bash function and `sync-workspace.sh` with `scripts/sync_manifest.py`
  - Single source of truth for which files to sync and what transformations to apply
  - `prepare-build.sh` and `just sync-workspace` both call the same manifest
- **Namespace-prefixed Cursor skill names** ([#67](https://github.com/vig-os/devcontainer/issues/67))
  - Renamed all 15 skills with colon-separated namespace prefixes (`issue:`, `design:`, `code:`, `git:`, `ci:`, `pr:`)
  - Enables filtering by namespace when invoking skills (e.g., typing `code:` shows implementation skills)
- **`--org` flag for install script** ([#33](https://github.com/vig-os/devcontainer/issues/33))
  - Allows overriding the default organization name (default: `vigOS`)
  - Passes `ORG_NAME` as environment variable to the container
  - Usage: `curl -sSf ... | bash -s --org MyOrg -- ~/my-project`
  - Unit tests for `--org` flag in help, default value, and custom override
- **Virtual environment prompt renaming** ([#34](https://github.com/vig-os/devcontainer/issues/34))
  - Post-create script updates venv prompt from "template-project" to project short name
  - Integration test verifies venv activate script does not contain "template-project"
- **BATS (Bash Automated Testing System) shell testing framework** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - npm dependencies for bats, bats-support, bats-assert, and bats-file
  - `test-bats` justfile task and requirements configuration
  - `test_helper.bash` supporting both local (node_modules) and CI (BATS_LIB_PATH) library resolution
  - CI integration in setup-env and test-project actions with conditional parallel execution via GNU parallel
  - Comprehensive BATS test suites for build, clean, init, install, and prepare-build scripts
  - Tests verify script structure, argument parsing, function definitions, error handling, and OS/runtime detection patterns
- **Post-install user configuration step** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Automatically call copy-host-user-conf.sh after workspace initialization
  - `run_user_conf()` helper for host-side setup (git, ssh, gh)
  - Integration tests for .devcontainer/.conf/ directory creation and expected config files
- **Git repository initialization in install script** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - `setup_git_repo()` function to initialize git if missing
  - Creates initial commit "chore: initial project scaffold" for new repos
  - Automatically creates main and dev branches
  - `test-install` justfile recipe for running install tests
  - Integration tests for git repo initialization, branches, and initial commit
- **Commit message standardization** ([#36](https://github.com/vig-os/devcontainer/issues/36))
  - Commit message format: `type(scope)!: subject` with mandatory `Refs: #<issue>` line
  - Documentation: `docs/COMMIT_MESSAGE_STANDARD.md` defining format, approved types (feat, fix, docs, chore, refactor, test, ci, build, revert, style), and traceability requirements
  - Validation script: `scripts/validate_commit_msg.py` enforcing the standard
  - Commit-msg hook: `.githooks/commit-msg` runs validation on every commit
  - Pre-commit integration: commit-msg stage hook in `.pre-commit-config.yaml`
  - Git commit template: `.gitmessage` with format placeholder
  - Cursor integration: `.cursor/rules/commit-messages.mdc` and `.cursor/commands/commit-msg.md` for AI-assisted commit messages
  - Workspace template: all commit message tooling included in `assets/workspace/` for new projects
  - Tests: `tests/test_validate_commit_msg.py` with comprehensive validation test cases
- **nano text editor** in devcontainer image ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Chore Refs exemption** in commit message standard ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - `chore` commits may omit the `Refs:` line when no issue or PR is directly related
  - Validator updated with `REFS_OPTIONAL_TYPES` to accept chore commits without Refs
- **Dependency review allowlist entry** for debug@0.6.0 ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Added GHSA-9vvw-cc9w-f27h exception to `.github/dependency-review-allow.txt`
  - Addresses ReDoS vulnerability in transitive test dependency (bats-assert → verbose → debug)
  - High risk severity but isolated to CI/development environment with expiration 2026-11-17
|- **Dependency review exception for legacy test vulnerabilities** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Comprehensive acceptance register for 9 transitive vulnerabilities in unmaintained BATS test framework dependencies
  - All 9 vulnerabilities are isolated to CI/development environment (engine.io, debug, node-uuid, qs, tough-cookie, ws, xmlhttprequest, form-data)
  - Formal risk assessments and mitigations documented in `SECURITY.md` and `.github/dependency-review-allow.txt`
  - Expiration-enforced exceptions with 2026-11-17 expiration date to force periodic re-evaluation

- **Bandit and Safety security scanning** ([#37](https://github.com/vig-os/devcontainer/issues/37), [#50](https://github.com/vig-os/devcontainer/issues/50))
  - Bandit pre-commit hook for medium/high/critical severity Python code analysis
  - CI pipeline job with Bandit static analysis and Safety dependency vulnerability scanning
  - Reports uploaded as artifacts (30-day retention) with job summary integration
- **Scheduled weekly security scan workflow** (`security-scan.yml`) ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Full Trivy vulnerability scan (all severities) against `dev` branch every Monday 06:00 UTC
  - SBOM generation (CycloneDX) and SARIF upload to GitHub Security tab
  - Non-blocking: catches newly published CVEs between pull requests
- **Non-blocking unfixed vulnerability reporting in CI** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Additional CI scan step reports unfixed HIGH/CRITICAL CVEs for awareness without blocking the pipeline
- **Comprehensive `.trivyignore` vulnerability acceptance register** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Formal medtech-compliant register (IEC 62304 / ISO 13485) documenting 10 accepted CVEs
  - Each entry includes risk assessment, exploitability justification, fix status, and mitigation
  - 6-month expiration dates enforce periodic re-evaluation
- **Expiration-enforced dependency-review exceptions** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Allow GHSA-wvrr-2x4r-394v (bats-file false positive) via `.github/dependency-review-allow.txt`
  - CI validation step parses expiration dates and fails the pipeline when exceptions expire, forcing periodic review
- **Branch name enforcement as a pre-commit hook** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - New `branch-name` hook enforcing `<type>/<issue>-<summary>` convention (e.g. `feature/38-standardize-branching-strategy-enforcement`)
  - Pre-commit configuration updated in repo and in workspace assets (`.pre-commit-config.yaml`, `assets/workspace/.pre-commit-config.yaml`)
  - Integration tests added for valid and invalid branch names
- **Cursor rules for branch naming and issue workflow** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - `.cursor/rules/branch-naming.mdc`: topic branch naming format, branch types, workflow for creating/linking branches via `gh issue develop`
  - Guidelines for inferring branch type from issue labels and deriving short summary from issue title
- **Release cycle documentation** ([#38](https://github.com/vig-os/devcontainer/issues/38), [#48](https://github.com/vig-os/devcontainer/issues/48))
  - `docs/RELEASE_CYCLE.md` with complete release workflow, branching strategy, and CI/CD integration
  - Cursor commands: `after-pr-merge.md`, `submit-pr.md`
- **pip-licenses** installed system-wide with version verification test ([#43](https://github.com/vig-os/devcontainer/issues/43))
- **just-lsp** language server and VS Code extension for Just files ([#44](https://github.com/vig-os/devcontainer/issues/44))
- **Automated release cycle** ([#48](https://github.com/vig-os/devcontainer/issues/48))
  - `prepare-release` and `finalize-release` justfile commands triggering GitHub Actions workflows
  - `prepare-changelog.py` script with prepare, validate, reset, and finalize commands for CHANGELOG automation
  - `reset-changelog` justfile command for post-merge CHANGELOG cleanup
  - `prepare-release.yml` GitHub Actions workflow: validates semantic version, creates release branch, prepares CHANGELOG
  - Unified `release.yml` pipeline: validate → finalize → build/test → publish → rollback
  - Comprehensive test suite in `tests/test_release_cycle.py`
- **CI testing infrastructure** ([#48](https://github.com/vig-os/devcontainer/issues/48))
  - `ci.yml` workflow replacing `test.yml` with streamlined project checks (lint, changelog validation, utility and release-cycle tests)
  - Reusable composite actions: `setup-env`, `build-image`, `test-image`, `test-integration`, `test-project`
  - Artifact transfer between jobs for consistent image testing
  - Retry logic across all CI operations for transient failure handling
- **GitHub Actions SHA pinning enforcement** ([#50](https://github.com/vig-os/devcontainer/issues/50))
  - `scripts/check_action_pins.py` pre-commit hook and CI check ensuring all GitHub Actions and Docker actions reference commit SHAs
  - Comprehensive test suite in `tests/test_check_action_pins.py`
- **CODEOWNERS** for automated review assignment ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **SECURITY.md** with vulnerability reporting procedures and supported version policy ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **OpenSSF Scorecard workflow** (`scorecard.yml`) for supply chain security scoring ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **CodeQL analysis workflow** (`codeql.yml`) for automated static security analysis ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Dependabot configuration** for automated dependency update PRs with license compliance monitoring ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Vulnerability scanning and dependency review** in CI pipeline with non-blocking MEDIUM severity reporting ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **SBOM generation, container signing, and provenance attestation** in release and CI pipelines ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Edge case tests** for changelog validation, action SHA pinning, and install script ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **`vig-utils` reusable CLI utilities package** ([#51](https://github.com/vig-os/devcontainer/issues/51))
  - Python package in `packages/vig-utils/` for shared validation and build utilities
  - `validate_commit_msg` module: enforces commit message format and references standards
    - Configurable commit scopes validation: scope list can be customized per project
    - Scopes are optional by default; if used, must be in the approved list
    - Support for multiple scopes, comma-separated (e.g., `feat(api, cli): add feature`)
    - Support for GitHub auto-linked issue references (e.g., PR cross-repo links)
    - Comprehensive test suite with edge case coverage for PR and cross-repo issue links
  - `prepare_changelog` module: CHANGELOG management and validation
  - `check_action_pins` module: GitHub Actions SHA pinning enforcement
  - Integrated into CI/CD pipeline and pre-commit hooks as standard Python package
  - Package version tests verify installation and correct versioning
- **Code coverage reporting in CI** ([#52](https://github.com/vig-os/devcontainer/issues/52))
  - Code coverage measurement integrated into test action workflow
  - Coverage threshold raised to 50% for unit tests
  - Expanded unit tests to improve overall test coverage
- **File duplication detection and elimination** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Build-time manifest system detects and removes duplicated workspace assets
  - Replaces duplicated files with sync manifest entries, reducing redundancy
  - Workspace assets now synchronized from central manifest during build preparation
  - GitHub workflow templates for devcontainer projects included in sync manifest
  - Automated npm dependency management with centralized version pinning in `.github/package.json`
  - Extract build preparation into dedicated `prepare-build.sh` script with manifest sync
  - SHA-256 checksum verification tests for synced files via `parse_manifest` fixture and `test_manifest_files`
- **GitHub workflow templates for devcontainer projects** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Reusable workflow templates for continuous integration and deployment
  - Support for projects using devcontainer-based development environments
- **Centralized `@devcontainers/cli` version management** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Version pinned in `.github/package.json` for consistent behavior across workflows and builds
  - Ensures reproducibility across build and setup environments
- **`--require-scope` flag for `validate-commit-msg`** ([#58](https://github.com/vig-os/devcontainer/issues/58))
  - New CLI flag to mandate that all commits include at least one scope (e.g. `feat(api): ...`)
  - When enabled, scopeless commits (e.g. `feat: ...`) are rejected at the commit-msg stage
  - Comprehensive tests added to `test_validate_commit_msg.py`
- **`post-start.sh` devcontainer lifecycle script** ([#60](https://github.com/vig-os/devcontainer/issues/60))
  - New script runs on every container start (create + restart)
  - Handles Docker socket permissions and dependency sync via `just sync`
  - Replaces inline `postStartCommand` in `devcontainer.json`
- **Dependency sync delegated to `just sync` across all lifecycle hooks** ([#60](https://github.com/vig-os/devcontainer/issues/60))
  - `post-create.sh`, `post-start.sh`, and `post-attach.sh` now call `just sync` instead of `uv sync` directly
  - `justfile.base` `sync` recipe updated with `--all-extras --no-install-project` flags and `pyproject.toml` guard
  - Abstracts toolchain details so future dependency managers only need a recipe change

- **Git initialization default branch** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Updated git initialization to set the default branch to 'main' instead of 'master'
  - Consolidated Podman installation with other apt commands in Containerfile
- **CI release workflow uses GitHub API** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Replace local git operations with GitHub API in prepare-release workflow
  - Use commit-action for CHANGELOG updates instead of local git
  - Replace git operations with GitHub API in release finalization flow
  - Simplify rollback and tag deletion to use gh api
  - Add sync-dependencies input to setup-env action (default: false)
  - Remove checkout step from setup-env; callers must checkout explicitly
  - Update all workflow callers to pass sync-dependencies input
  - Update CI security job to use uv with setup-env action
- **Commit message guidelines** - updated documentation ([#36](https://github.com/vig-os/devcontainer/issues/37))
- **Expected version checks** - updated ruff and pre-commit versions in test suite ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Bumped `actions/create-github-app-token`** from v1 to v2 across workflows with updated SHA pins ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Pinned `@devcontainers/cli`** to version 0.81.1 in CI for consistent behavior ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **CI and release Trivy scans gate on fixable CVEs only** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Added `ignore-unfixed: true` to blocking scan steps in `ci.yml` and `release.yml`
  - Unfixable CVEs no longer block the pipeline; documented in `.trivyignore` with risk assessments
- **Updated pre-commit hook configuration in the devcontainer** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - Exclude issue and template docs from .github_data
  - Autofix shellcheck
  - Autofix pymarkdown
  - Add license compliance check
- **Renamed `publish-container-image.yml` to `release.yml`** and expanded into unified release pipeline ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Merged `prepare-build.sh` into `build.sh`** — consolidated directory preparation, asset copying, placeholder replacement, and README updates into a single entry point ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Consolidated test files by domain** — reorganized from 6 files to 4 (`test_image.py`, `test_integration.py`, `test_utils.py`, `test_release_cycle.py`) ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Replaced `setup-python-uv` with flexible `setup-env` composite action** supporting optional inputs for podman, Node.js, and devcontainer CLI ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Reduced `sync-issues` workflow triggers** — removed `edited` event type from issues and pull_request triggers ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Release workflow pushes tested images** instead of rebuilding after tests pass ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Updated CONTRIBUTE.md** release workflow documentation to match automated process ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **CodeQL Action v3 → v4 upgrade**
  - Updated all CodeQL Action references from v3 (deprecated Dec 2026) to v4.32.2
  - Updated in `.github/workflows/codeql.yml`, `security-scan.yml`, and `ci.yml`
  - Uses commit hash `45cbd0c69e560cd9e7cd7f8c32362050c9b7ded2` for integrity
- **Sync-issues workflow output directory** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Changed output directory from '.github_data' to 'docs' for better project structure alignment
- **Workspace `validate-commit-msg` hook configured strict-by-default** ([#58](https://github.com/vig-os/devcontainer/issues/58))
  - `assets/workspace/.pre-commit-config.yaml` now ships with explicit `args` instead of commented-out examples
  - Default args enable type enforcement, scope enforcement with `--require-scope`, and `chore` refs exemption
  - Link to `vig-utils` README added as a comment above the hook for discoverability
- **Refresh pinned Python base image digest** ([#213](https://github.com/vig-os/devcontainer/issues/213))
  - Update `python:3.12-slim-bookworm` pinned digest in `Containerfile` to the latest upstream value while keeping the same tag
- **Pre-commit hook removal transform preserves section comments** ([#171](https://github.com/vig-os/devcontainer/issues/171))
  - `scripts/transforms.py` keeps section comments intact while removing configured hooks during manifest sync
  - `scripts/manifest.toml` and related sync/test updates keep workspace pre-commit outputs aligned with container CI workflow changes
- **Migrate shared scripts into `vig-utils` package entrypoints** ([#217](https://github.com/vig-os/devcontainer/issues/217), [#161](https://github.com/vig-os/devcontainer/issues/161), [#179](https://github.com/vig-os/devcontainer/issues/179))
  - Shell scripts (`check-skill-names.sh`, `derive-branch-summary.sh`, `resolve-branch.sh`, `setup-labels.sh`) bundled inside `vig_utils.shell` and exposed as `vig-<name>` CLI entrypoints
  - Python scripts (`gh_issues.py`, `check-agent-identity.py`, `check-pr-agent-fingerprints.py`, `prepare-commit-msg-strip-trailers.py`) migrated into `vig-utils` modules with entrypoints
  - Agent fingerprint helpers consolidated into shared `vig_utils.utils` module
  - Callers (justfiles, pre-commit hooks, CI workflows) switched from direct script paths to `vig-utils` entrypoints
- **Restructure workspace justfile into devc/project split** ([#219](https://github.com/vig-os/devcontainer/issues/219))
  - Rename `justfile.base` to `justfile.devc` and keep devcontainer lifecycle recipes there
  - Move project-level recipes (`lint`, `format`, `precommit`, `test`, `sync`, `update`, `clean-artifacts`, `log`, `branch`) into `justfile.project`
  - Add tracked `justfile.local` template for personal recipes while keeping it ignored in downstream workspaces, and update workspace imports/manifests to the new structure
- **Update base Python image and GitHub Actions dependencies** ([#240](https://github.com/vig-os/devcontainer/issues/240))
  - Containerfile: pin `python:3.12-slim-bookworm` to latest digest
  - Bump trivy CLI v0.69.2 → v0.69.3, trivy-action v0.33.1 → v0.35.0
  - Update astral-sh/setup-uv, taiki-e/install-action, docker/build-push-action, github/codeql-action, actions/dependency-review-action, actions/attest-build-provenance
- **Bump GitHub CLI to 2.88.x**
  - Update expected `gh` version in image tests from 2.87 to 2.88
- **Manifest sync includes `sync-main-to-dev` workflow** ([#278](https://github.com/vig-os/devcontainer/issues/278))
  - Add `.github/workflows/sync-main-to-dev.yml` to `scripts/manifest.toml` so workspace sync includes the release-to-dev PR automation workflow


### Removed

- **`post-release.yml`** — replaced by `sync-main-to-dev.yml` ([#172](https://github.com/vig-os/devcontainer/issues/172))
- **`scripts/prepare-build.sh`** — merged into `build.sh` ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **`scripts/sync-prs-issues.sh`** — deprecated sync script ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **`test.yml` workflow** — replaced by `ci.yml` ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Stale `.github_data/` directory** — 98 files superseded by `docs/issues/` and `docs/pull-requests/` ([#91](https://github.com/vig-os/devcontainer/issues/91))
- **Legacy standalone script copies** ([#217](https://github.com/vig-os/devcontainer/issues/217))
  - Removed `scripts/check-agent-identity.py`, `scripts/check-skill-names.sh`, `scripts/derive-branch-summary.sh`, `scripts/resolve-branch.sh` — now in `vig-utils`
  - Removed `assets/workspace/.devcontainer/scripts/gh_issues.py`, `check-pr-agent-fingerprints.py`, `prepare-commit-msg-strip-trailers.py` — now in `vig-utils`
  - Removed `scripts/utils.py` shim — superseded by `vig_utils.utils`

### Fixed

- **`just` default recipe hidden by lint recipe** ([#254](https://github.com/vig-os/devcontainer/issues/254))
  - The `default` recipe must appear before any other recipe in the justfile; `lint` was placed first, shadowing the recipe listing
  - Moved `default` recipe above `lint` to restore `just` with no arguments showing available recipes
- **Broken `gh-issues --help` guard in justfile recipe** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - `gh-issues` CLI has no `--help` flag, so the availability check always failed even when the binary was installed
  - Removed the broken guard; binary availability is now verified by the image test suite
- **Smoke-test redeploy preserves synced docs directories** ([#262](https://github.com/vig-os/devcontainer/issues/262))
  - `init-workspace.sh --smoke-test` now excludes `docs/issues/` and `docs/pull-requests/` from `rsync --delete`
  - Re-deploying smoke assets no longer removes docs synced by `sync-issues`
- **Prepare-release uses scoped app tokens for protected branch writes** ([#268](https://github.com/vig-os/devcontainer/issues/268))
  - `prepare-release.yml` now uses `COMMIT_APP_*` for git/ref and `commit-action` operations that touch `dev` and release refs
  - Draft PR creation in prepare-release now uses `RELEASE_APP_*` token scope for pull-request operations
- **generate-docs picks up unreleased TBD version on release branches** ([#271](https://github.com/vig-os/devcontainer/issues/271))
  - `get_version_from_changelog()` and `get_release_date_from_changelog()` now skip entries without a concrete release date
- **PR fingerprint check false positives on plain-text AI tool mentions** ([#274](https://github.com/vig-os/devcontainer/issues/274))
  - `contains_agent_fingerprint` now restricts name matching to attribution-context lines (e.g. "generated by", "authored by") instead of scanning the entire content
  - Wire up `allow_patterns` from `agent-blocklist.toml` to strip known-safe text (dotfile paths, doc filenames) before checking
- **Release candidate publish retags loaded images before push** ([#281](https://github.com/vig-os/devcontainer/issues/281))
  - `release.yml` now tags `ghcr.io/vig-os/devcontainer:X.Y.Z-arch` artifacts as `X.Y.Z-rcN-arch` before `docker push` in candidate runs
  - Prevents publish failures caused by pushing candidate tags that were never created locally after `docker load`
- **Pinned commit-action to the malformed path fix release** ([#286](https://github.com/vig-os/devcontainer/issues/286))
  - Updated smoke-test and release-related workflows to `vig-os/commit-action@c0024cbad0e501764127cccab732c6cd465b4646` (`v0.1.5`)
  - Resolves failures when commit-action receives `FILE_PATHS: .` and accidentally includes invalid `.git/*` tree paths
- **Smoke-test deploy commit no longer references non-local issue IDs** ([#284](https://github.com/vig-os/devcontainer/issues/284))
  - `assets/smoke-test/.github/workflows/repository-dispatch.yml` no longer injects `Refs: #258` into automated `chore: deploy <tag>` commits in the smoke-test repository
  - Added maintainer note that workflow-template changes require manual redeploy to `vig-os/devcontainer-smoke-test` and promotion through PRs to `main`
- **Install name sanitization trims invalid package boundaries** ([#291](https://github.com/vig-os/devcontainer/issues/291))
  - `install.sh` now normalizes sanitized project names to ensure they start/end with alphanumeric characters before passing `SHORT_NAME`
  - `init-workspace.sh` mirrors the same normalization so generated `pyproject.toml` names cannot end with separators like `_`

### Security

- **Eliminated 13 transitive vulnerabilities in BATS test dependencies** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Bumped bats-assert from v2.1.0 to v2.2.0, which dropped a bogus runtime dependency on the `verbose` npm package
  - Removed entire transitive dependency tree: engine.io, debug, node-uuid, qs, tough-cookie, ws, xmlhttprequest, form-data, request, sockjs, and others (50+ packages reduced to 5)
  - Cleaned 13 now-unnecessary GHSA exceptions from `.github/dependency-review-allow.txt`
- **Go stdlib CVEs from gh binary accepted and documented** ([#37](https://github.com/vig-os/devcontainer/issues/37))
- CVE-2025-68121, CVE-2025-61726, CVE-2025-61728, CVE-2025-61730 added to `.trivyignore`
- Vulnerabilities embedded in statically-linked GitHub CLI binary; low exploitability in devcontainer context
- Each entry includes risk assessment, justification, and 3-month expiration date to force re-review
- Awaiting upstream `gh` release with Go 1.25.7 or later
- **GHSA-wvrr-2x4r-394v (bats-file false positive) accepted in dependency review** ([#37](https://github.com/vig-os/devcontainer/issues/37))
- Added to `.github/dependency-review-allow.txt` with 6-month expiration date enforced by CI
- **Upgraded pip** in Containerfile to fix CVE-2025-8869 (symbolic link extraction vulnerability) ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Digest-pinned base image** (`python:3.12-slim-bookworm`) with SHA256 checksum verification for all downloaded binaries and `.trivyignore` risk-assessment policy in Containerfile ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Minisign signature verification** for cargo-binstall downloads ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **GitHub Actions and Docker actions pinned to commit SHAs** across all workflows ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Pre-commit hook repos pinned to commit SHAs** ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Workflow permissions hardened** with least-privilege principle and explicit token scoping ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Input sanitization** — inline expression interpolation replaced with environment variables in workflow run blocks to prevent injection ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Update vulnerable Python dependencies** ([#88](https://github.com/vig-os/devcontainer/issues/88))
  - Add uv constraints for transitive dependencies: `urllib3>=2.6.3`, `filelock>=3.20.3`, and `virtualenv>=20.36.1`
  - Regenerate `uv.lock` with patched resolutions (`urllib3 2.6.3`, `filelock 3.25.0`, `virtualenv 21.1.0`)
- **Temporary Trivy exception for CVE-2025-15558 in gh binary** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Added `CVE-2025-15558` to `.trivyignore` with risk assessment, upstream dependency context, and an expiration date
  - Keeps CI vulnerability scan unblocked while waiting for an upstream `gh` release that includes the patched `github.com/docker/cli` dependency

## [0.2.1](https://github.com/vig-os/devcontainer/releases/tag/0.2.1) - 2026-01-28

### Added

- **Manual target branch specification** for sync-issues workflow
  - Added `target-branch` input to `workflow_dispatch` trigger for manually specifying commit target branch
  - Allows explicit branch selection when triggering workflow manually (e.g., `main`, `dev`)
- **cargo-binstall** in Containerfile
  - Install via official install script; binaries in `/root/.cargo/bin` with `ENV PATH` set
  - Version check in `tests/test_image.py`
- **typstyle** linting
  - Install via `cargo-binstall` in Containerfile
  - Version check in test suite
  - Pre-commit hook configuration for typstyle
- **Just command runner** installation and version verification
  - Added installation of the latest version of `just` (1.46.0) in the Containerfile
  - Added tests to verify `just` installation and version in `test_image.py`
  - Added integration tests for `just` recipes (`test_just_default`, `test_just_help`, `test_just_info`, `test_just_pytest`)
- **GitHub Actions workflow for multi-architecture container image publishing** (`.github/workflows/release.yml`)
  - Automated build and publish workflow triggered on semantic version tags (X.Y.Z)
  - Multi-architecture support (amd64, arm64) with parallel builds on native runners
  - Image testing before push: runs `pytest tests/test_image.py` against built images
  - Manual dispatch support for testing workflow changes without pushing images (default version: 99.0.1)
  - Optional manual publishing: `workflow_dispatch` can publish images/manifests when `publish=true` (default false)
  - Architecture validation and dynamic selection: users can specify single or multiple architectures (amd64, arm64) with validation
  - Comprehensive error handling and verification steps
  - OCI-standard labels via `docker/metadata-action`
  - Build log artifacts for debugging (always uploaded for manual dispatch and on failure)
  - Multi-architecture manifest creation for automatic platform selection
  - Centralized version extraction job for reuse across build and manifest jobs
  - Concurrency control to prevent duplicate builds
  - Timeout protection (60 minutes for builds, 10 minutes for manifest)
- **GitHub Actions workflow for syncing issues and PRs** (`.github/workflows/sync-issues.yml`)
  - Automated sync of GitHub issues and PRs to markdown files in `.github_data/`
  - Runs on schedule (daily), manual trigger, issue events, and PR events
  - Smart branch selection: commits to `main` when PRs are merged into `main`, otherwise commits to `dev`
  - Cache-based state management to track last sync timestamp
  - Force update option for manual workflow dispatch
- **Enhanced test suite**
  - Added utility function tests (`tests/test_utils.py`) for `sed_inplace` and `update_version_line`
  - Improved test organization in justfile with grouped test commands (`just test-all`, `just test-image`, `just test-utils`)
- **Documentation improvements**
  - Added workflow status badge to README template showing publish workflow status
  - Simplified contribution guidelines by removing QEMU build instructions

### Changed

- **Sync-issues workflow branch protection bypass**
  - Added GitHub App token generation step using `actions/create-github-app-token@v2`
  - Updated commit-action to use GitHub App token for bypassing branch protection rules
  - Updated `vig-os/commit-action` from `v0.1.1` to `v0.1.3`
  - Changed commit-action environment variable from `GITHUB_TOKEN`/`GITHUB_REF` to `GH_TOKEN`/`TARGET_BRANCH` to match action's expected interface
- **Devcontainer test fixtures** (`tests/conftest.py`)
  - Shared helpers for `devcontainer_up` and `devcontainer_with_sidecar`: path resolution, env/SSH, project yaml mount, run up, teardown
  - `devcontainer_with_sidecar` scope set to session (one bring-up per session for sidecar tests)
  - Cleanup uses same approach as `just clean-test-containers` (list containers by name, `podman rm -f`) so stacks are torn down reliably
  - Redundant imports removed; fixture logic simplified for maintainability
- **Build process refactoring**
  - Separated build preparation into dedicated `prepare-build.sh` script
  - Handles template replacement, asset copying, and README version updates
  - Improved build script with `--no-cache` flag support and better error handling
- **Development workflow streamlining**
  - Simplified contribution guidelines: removed QEMU build instructions and registry testing complexity
  - Consolidated test commands in justfile for better clarity
  - Updated development setup instructions to reflect simplified workflow
- **Package versions**
  - Updated `ruff` from 0.14.10 to 0.14.11 in test expectations

### Removed

- **Deprecated justfile test recipe and test**
  - Removed deprecated test command from justfile
  - Removed deprecated test for default recipe in justfile (`TestJustIntegration.test_default_recipe_includes_check`)
- **Registry testing infrastructure** (moved to GitHub Actions workflow)
  - Removed `scripts/push.sh` (455 lines) - functionality now in GitHub Actions workflow
  - Removed `tests/test_registry.py` (788 lines) - registry tests now in CI/CD pipeline
  - Removed `scripts/update_readme.py` (80 lines) - README updates handled by workflow
  - Removed `scripts/utils.sh` (75 lines) - utilities consolidated into other scripts
  - Removed `just test-registry` command - no longer needed with automated workflow

### Fixed

- **Multi-platform container builds** in Containerfile
  - Removed default value from `TARGETARCH` ARG to allow Docker BuildKit's automatic platform detection
  - Fixes "Exec format error" when building for different architectures (amd64, arm64)
  - Ensures correct architecture-specific binaries are downloaded during build
- **Image tagging after podman load** in publish workflow
  - Explicitly tag loaded images with expected name format (`ghcr.io/vig-os/devcontainer:VERSION-ARCH`)
  - Fixes test failures where tests couldn't find the image after loading from tar file
  - Ensures proper image availability for testing before publishing
- **GHCR publish workflow push permissions**
  - Authenticate to `ghcr.io` with the repository owner and token context, and set explicit job-level `packages: write` permissions to prevent `403 Forbidden` errors when pushing layers.
- **Sync-issues workflow branch determination logic**
  - Fixed branch selection to prioritize manual `target-branch` input when provided via `workflow_dispatch`
  - Improved branch detection: manual input → PR merge detection → default to `dev`
- **Justfile default recipe conflict**
  - Fixed multiple default recipes issue by moving `help` command to the main justfile
  - Removed default command from `justfile.project` and `justfile.base` to prevent conflicts
  - Updated just recipe tests to handle variable whitespace in command output formatting
- **Invalid docker-compose.project.yaml**
  - Added empty services section to docker-compose.project.yaml to fix YAML validation
- **Python import resolution in tests**
  - Fixed import errors in `tests/test_utils.py` by using `importlib.util` for explicit module loading
  - Improved compatibility with static analysis tools and linters
- **Build script improvements**
  - Fixed shellcheck warnings by properly quoting script paths
  - Improved debug output and error messages

## [0.2.0](https://github.com/vig-os/devcontainer/releases/tag/0.2.0) - 2026-01-06

### Added

- **Automatic version check** for devcontainer updates with DRY & SOLID design
  - Checks GitHub API for new releases and notifies users when updates are available
  - Silent mode with graceful failure (no disruption to workflow)
  - Configurable check interval (default: 24 hours) with spam prevention
  - Mute notifications for specified duration (`just check 7d`, `1w`, `12h`, etc.)
  - Enable/disable toggle (`just check on|off`)
  - One-command update: `just update` downloads install script and updates template files
  - Configuration stored in `.devcontainer/.local/` (gitignored, machine-specific)
  - Auto-runs on `just` default command (can be disabled)
  - Comprehensive test suite (`tests/test_version_check.py`) with 24 tests covering all functionality
- **One-line install script** (`install.sh`) for curl-based devcontainer deployment
  - Auto-detection of podman/docker runtime (prefers podman)
  - Auto-detection and sanitization of project name from folder name (lowercase, underscores)
  - OS-specific installation instructions when runtime is missing (macOS, Ubuntu, Fedora, Arch, Windows)
  - Runtime health check with troubleshooting advice (e.g., "podman machine start" on macOS)
  - Flags: `--force`, `--version`, `--name`, `--dry-run`, `--docker`, `--podman`, `--skip-pull`
- `--no-prompts` flag for `init-workspace.sh` enabling non-interactive/CI usage
- `SHORT_NAME` environment variable support in `init-workspace.sh`
- Test suite for install script (`tests/test_install_script.py`) with unit and integration tests
- `just` as build automation tool (replaces `make`)
- Layered justfile architecture: `justfile.base` (managed), `justfile.project` (team-shared), `justfile.local` (personal)
- Generic sidecar passthrough: `just sidecar <name> <recipe>` for executing commands in sidecar containers
- Documentation generation system (`docs/generate.py`) with Jinja2 templates
- Python project template with `pyproject.toml` and standard structure (`src/`, `tests/`, `docs/`)
- Pre-built Python virtual environment with common dev/science dependencies (numpy, scipy, pandas, matplotlib, pytest, jupyter)
- Auto-sync Python dependencies on container attach via `uv sync`
- `UV_PROJECT_ENVIRONMENT` environment variable for instant venv access without rebuild
- `pip-licenses` pre-commit hook for dependency license compliance checking (blocks GPL-3.0/AGPL-3.0)
- Pre-flight container cleanup check in test suite with helpful error messages
- `just clean-test-containers` recipe for removing lingering test containers
- `PYTEST_AUTO_CLEANUP` environment variable for automatic test container cleanup
- `docker-compose.project.yaml` for team-shared configuration (git-tracked, preserved during upgrades)
- `docker-compose.local.yaml` for personal configuration (git-ignored, preserved during upgrades)
- Build-time manifest generation for optimized placeholder replacement
- `tests/CLEANUP.md` documentation for test container management

### Changed

- `ORG_NAME` now defaults to `"vigOS/devc"` instead of requiring user input
- `init-workspace.sh` now escapes special characters in placeholder values (fixes sed errors with `/` in ORG_NAME)
- Documentation updated with curl-based install as primary quick start method
- **BREAKING**: Replaced `make` with `just` - all build commands now use `just` (e.g., `just test`, `just build`, `just push`)
- **Versioning scheme**: Switched from X.Y format to Semantic Versioning (X.Y.Z format).
All new releases use MAJOR.MINOR.PATCH format (e.g., 0.2.0).
The previous v0.1 release is kept as-is for backwards compatibility.
- **Package versions**: Bumped tool and project versions from previous release:
  - `uv` (0.9.17 → 0.9.21)
  - `gh` (2.83.1 → 2.83.2)
  - `pre-commit` (4.5.0 → 4.5.1)
  - `ruff` (0.14.8 → 0.14.10)
- VS Code Python interpreter now points to pre-built venv (`/root/assets/workspace/.venv`)
- Test container cleanup check runs once at start of `just test` instead of each test phase
- **BREAKING**: Docker Compose file hierarchy now uses `project.yaml` and `local.yaml` instead of `override.yml`
- Socket detection prioritizes Podman over Docker Desktop on macOS and Linux
- `{{TAG}}` placeholder replacement moved to container with build-time manifest generation (significantly faster initialization)
- Socket mount configuration uses environment variable with fallback: `${CONTAINER_SOCKET_PATH:-/var/run/docker.sock}`
- `initialize.sh` writes socket path to `.env` file instead of modifying YAML directly
- `init-workspace.sh` simplified: removed cross-platform `sed` handling (always runs in Linux)

### Removed

- Deprecated `version` field from all Docker Compose files
- `:Z` SELinux flag from socket mounts (incompatible with macOS socket files)
- `docker-compose.override.yml` (replaced by `project.yaml` and `local.yaml`)
- `docker-compose.sidecar.yaml` (merged into main `docker-compose.yml`)

### Fixed

- Test failures from lingering containers between test phases
(now detected and reported before test run; added `PYTEST_SKIP_CONTAINER_CHECK` environment variable)
- Improved error messages for devcontainer startup failures
- SSH commit signing: Changed `user.signingkey` from file path to email identifier to support SSH agent forwarding.
  Git now uses the SSH agent for signing by looking up the email in allowed-signers and matching with the agent key.
- Fixed `gpg.ssh.allowedSignersFile` path to use container path instead of host path after copying git configuration.
- Automatically add git user email to allowed-signers file during setup to ensure commits can be signed and verified.
- macOS Podman socket mounting errors caused by SELinux `:Z` flag on socket files
- Socket detection during tests now matches runtime behavior (Podman-first)

## [0.1](https://github.com/vig-os/devcontainer/releases/tag/0.1) - 2025-12-10

### Core Image

- Development container image based on Python 3.12 (Debian Trixie)
- Multi-architecture support (AMD64, ARM64)
- System tools: git, gh (GitHub CLI), curl, openssh-client, ca-certificates
- Python tools: uv, pre-commit, ruff
- Pre-configured development environment with minimal overhead

### Devcontainer Integration

- VS Code devcontainer template with init-workspace script setting organization and project name
- Docker Compose orchestration for flexible container management
- Support for mounting additional folders via docker-compose.override.yml
- Container lifecycle scripts `post-create.sh`, `initialize.sh` and `post-attach.sh` for seamless development setup
- Automatic Git configuration synchronization from host machine
- SSH commit signing support with signature verification
- Focused `.devcontainer/README.md` with version tracking, lifecycle documentation, and workspace configuration guide
- User-specific `workspace.code-workspace.example` for multi-root VS Code workspaces (actual file is gitignored)

### Testing Infrastructure

- Three-tiered test suite: image tests, integration tests, and registry tests
- Automated testing with pytest and testinfra
- Registry tests with optimized minimal Containerfile (10-20s builds)
- Session-scoped fixtures for efficient test execution
- Comprehensive validation of push/pull/clean workflows
- Tests verify devcontainer README version in pushed images
- Helper function tests for README update utilities

### Automation and Tooling

- Justfile with build, test, push, pull, and clean recipes
- Automated version management and git tagging
- Automatic README.md updates with version and image size during releases
- Push script with multi-architecture builds and registry validation
- Setup script for development environment initialization
- `update_readme.py` helper script for patching README metadata (version, size, development reset)
- Automatic devcontainer README version updates during releases

### Documentation and Templates

- GitHub issue templates (bug report, feature request, task)
- Pull request template with comprehensive checklist
- Complete project documentation (README.md, CONTRIBUTE.md, TESTING.md)
- Detailed testing strategy and workflow documentation
- Push script updates README files in both project and assets
