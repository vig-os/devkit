---
type: issue
state: open
created: 2026-09-14T08:03:12Z
updated: 2026-09-14T08:15:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1621
comments: 1
labels: feature, area:workflow, effort:large, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-14T08:32:53.377Z
---

# [Issue 1621]: [[FEATURE] Hotfix release lane: cut release/X.Y.Z from main without going through dev](https://github.com/vig-os/devkit/issues/1621)

### Description

A hotfix lane for the gitflow release train: a new **`prepare-hotfix.yml`** workflow that cuts `release/X.Y.Z` directly from `main`, so an urgent fix (typically security) can ship as a patch release without carrying whatever `dev` has accumulated. The fix lands via a `bugfix/N-*` branch off the release branch (already sanctioned by the branch table in `docs/RELEASE_CYCLE.md`), then the **existing, unchanged** candidate/final/promote/abandon train runs, and `sync-main-to-dev.yml` closes the loop back to `dev`.

This design was evaluated against the full release machinery (audit of every dev-assumption in the five train workflows), alternatives, downstream scaffold impact, and testability. Summary below; the evaluation established that **everything downstream of prepare is genuinely base-agnostic** — `release.yml` (validate/finalize/vulnix-gate/publish/tag/smoke-dispatch/rollback), `promote-release.yml` (incl. RC cleanup), `abandon-release.yml`, and even `prepare-release-extension.yml` (the #1115 dev fast-forward fails safe by construction for a main-cut branch; its fallback no-ops) all work unchanged. Only prepare needs a counterpart.

### Problem Statement

Today the only path to `main` is the full cycle through `dev` (`prepare-release.yml` is dev-hardwired: `ref: dev` checkouts, a branch assert, the changelog freeze/reset on dev, branch cut from dev, dev-restoring rollback). When `dev` carries work not ready to release, an urgent fix on `main` — e.g. the security-register incidents (#1592, #1614) — has no supported lane: #1614-class issues on `main` stay open until the next full train. The gitflow hotfix path was described in the original design (issue #48) but never built.

### Proposed Solution

`prepare-hotfix.yml` (scaffold-shaped, repo specifics stay in the existing extension hook):

1. **Validate**: version is a patch increment of the highest stable tag reachable from `main`; no colliding `release/*` branch or tag. (Today nothing anywhere enforces version ordering — this also implicitly forbids "hotfix minors".)
2. **Cut** `release/X.Y.Z` at `main`'s head via COMMIT_APP (`POST /git/refs` — same mechanism, base-agnostic; no new token or bypass needed since the branch is still `release/*`).
3. **Seed** an empty `## [X.Y.Z] - TBD` section onto the *release branch* (never `main`) — `main`'s `## Unreleased` is always empty by construction (#590), so there is nothing to freeze; needs a small `prepare-changelog` insert subcommand. The fix PR fills the section (per the existing `release/*` changelog rule); add a finalize-time guard that the section is non-empty.
4. **Call the existing reusable `prepare-release-extension.yml`** with `branch_sha` = the seeded commit, so the workspace changelog mirror is re-synced on the branch (the dev-FF path provably skips; the dev fallback finds dev clean and no-ops).
5. **Open** the draft PR `release/X.Y.Z` → `main`.
6. **Rollback** = delete branch + close PR, nothing else — no dev mutation exists to undo (strictly simpler than `prepare-release.yml`'s rollback).

Candidate/final/promote/abandon then run byte-for-byte unchanged (`just publish-candidate`, `just finalize-release`, promote — dispatched on the release branch as today).

**Accepted, documented costs:**
- The post-hotfix `sync-main-to-dev` merge **will conflict on `CHANGELOG.md` (+ the workspace mirror) whenever `dev` is ahead** — inherent to any main-based hotfix: the regular cycle's conflict-free property is bought by the shared freeze commit, which cannot exist for content authored off `main`. It lands on the sync workflow's existing first-class manual-conflict lane. Document the resolution recipe (keep dev's `## Unreleased` + bullets, insert main's dated `[X.Y.Z]` section beneath it, rerun `sync_manifest.py sync`). Do **not** extend the sync auto-resolver to hand-written changelog content.
- Hotfixes still ride the full RC → smoke-release → promote gate. No expedite path — weakening the gate is a separate policy decision, not part of this feature.

**Runbook rules shipped with the lane:**
- (i) A hotfix promoted while a regular `release/*` train is in flight obligates an immediate cherry-pick of the fix into that release branch — else the next minor silently reintroduces the regression. (Alternative: prepare-time refusal when another `release/*` exists — see open questions.)
- (ii) Promote moves `:latest` unconditionally; promoting a patch below the currently-promoted version walks `:latest` backwards. Runbook rule at minimum; optional promote guard — see open questions.
- (iii) Expect the promote BEHIND-mergeability gate if anything lands on `main` mid-hotfix; recovery is merging `main` into the release branch (re-dismisses approval, #1474).

### Alternatives Considered

- **`base: dev|main` input on `prepare-release.yml`** — rejected. Threads conditionals through the most failure-prone workflow in the repo (#617/#1078/#1115/#1462 history), doubles its rollback state space, and breaks the workflow-model ADR's anchored dev→main render (the trunk render sed-retargets plain literals like `ref: dev`; an expression-based base defeats it and ships trunk repos a vestigial input). The two lanes share less than they appear to — the hotfix lane has no freeze, no dev wait-loop, no dev FF, and a trivial rollback.
- **Reusing the trunk-shaped prepare render as the gitflow hotfix entry** — dead on arrival. The trunk prepare is a trunk-*discipline* workflow: it freezes `## Unreleased` on its base and requires it non-empty — structurally never true on gitflow `main` — and its freeze commit targets `main` directly, which gitflow main protection rejects. Also the whole-file-twin class the ADR explicitly rejected.
- **Expedited regular train ("fix forward through dev")** — the zero-implementation status quo; fails precisely when a hotfix is most needed (dev far ahead / unstable). Remains the right call when dev ≈ main.

### Additional Context

**Downstream / scaffold phasing.** Devkit's own train and the consumer train in `assets/workspace/` are parallel implementations (root `release.yml` diverges from the split core/extension/publish asset by ~1900 lines) — so this is a two-phase feature:
- **Phase 1 (this issue):** the lane in devkit's root workflows, proving the choreography.
- **Phase 2 (follow-up issue):** port to `assets/workspace/`, wired as **copy-exclude under `DEVKIT_WORKFLOW=trunk`** (trunk releases already cut from main — the lane is redundant there; same mechanism as `sync-main-to-dev.yml`) and added to the `release` feature group (solo adopters unaffected by construction). Validate on `devkit-smoke-test` via the existing cross-repo gate harness — only possible *after* a devkit release ships the asset. Ship before it's needed: `workflow_dispatch` only works once the file is on the consumer's default branch, and adoption PRs merge to `dev`, so a consumer cannot adopt-and-use in the same emergency.

**Test plan (layered, cheapest first):**
- **Layer 0 — static:** actionlint/yamllint via the hook suite; new `tests/test_workflow_prepare_hotfix.py` in the existing `workflow_scaffold.load_workflow` pattern, pinning at minimum: no checkout/API path targets `dev`; dry-run gates every mutating job; rollback wiring restores the right branch; tag/branch preflight present; `abandon-release` PR discovery still matches (`--head release/$VERSION --base main` is already base-main); the sync-issues commit whitelist in rollback is preserved.
- **Layer 1 — dry-run dispatch from the feature branch:** feasible — GitHub registers workflows pushed on non-default branches (in-repo precedent: `spike-992-conditional-container.yml` is registered and exists on no default branch). `gh workflow run prepare-hotfix.yml --ref <feature-branch> -f version=… -f dry-run=true` exercises the validate/read path against live refs and real tokens, side-effect-free (Layer 0 pins the dry-run gating first).
- **Layer 2 — candidate-only rehearsal in devkit:** with **no train in flight**: real prepare-hotfix run (verify branch forked from `main`'s SHA, draft PR base `main`, **dev untouched**), trivial fix PR, CI green, `just publish-candidate`, then **`just abandon-release` — never finalize, never promote** (finalize creates the draft Release + tag; promote requires a *published* downstream final — the points of no return). Use the real next patch number. Leftovers: keep the RC git tags (numbering continuity is the collision guard; the real re-cut reclaims everything at its promote), and accept **one permanent published pre-release `X.Y.Z-rcN` on `devkit-smoke-test`** (the listener publishes it per candidate; immutable org-wide). Full leftover checklist in the evaluation.
- **First-real-use watchlist (un-rehearsable):** finalize/promote/merge-to-main and the sync-back leg only run on the first production hotfix — pre-pin with static tests, smoke-run `sync-main-to-dev`'s check job via its `workflow_dispatch` path, and monitor closely. Note: `release.yml` executes from the release branch's copy, which for a hotfix is **main's copy** — any `release.yml` change the lane needs must ride a normal train first.

**Groundwork already in place:** the branch guard and CI branch gate already accept `hotfix/`; `ci.yml` already runs on PRs to `release/**` and `main`; `abandon-release` is base-agnostic; the changelog synthesizer's last-stable-tag..HEAD window is *more* correct on a main-cut branch than on the gitflow lineage.

### Impact

- **Who benefits:** devkit maintainers first (urgent security patches to `main` while `dev` is ahead — the #1614 scenario); all gitflow consumers once Phase 2 ships.
- **Compatibility:** fully backward compatible — a new workflow file plus a `prepare-changelog` subcommand, small docs additions (`RELEASE_CYCLE.md` branch table, lifecycle diagram, hotfix section), and new tests. The existing train is untouched by design; `tests/test_workflow_prepare_extension.py` and `test_workflow_model.py` pins remain valid.

**Open questions to settle before implementation:**
1. Version policy: machine-enforce patch-increment-of-latest-main-tag (recommended), or operator-chosen with weaker validation?
2. Concurrent-train policy: allow with the cherry-pick obligation, or hard-refuse in validate when any other `release/*` branch exists (simplest/safest for a solo-maintainer org)?
3. `:latest` ordering: add a semver guard to `promote-release.yml` (refuse moving `:latest` backwards — widens blast radius beyond the new file), or runbook-only?
4. Dev-side changelog reconciliation: accept the manual sync conflict per hotfix (recommended), or pre-seed the same `[X.Y.Z] - TBD` header on dev for shared-context merging (reintroduces the dev-mutation + rollback coupling the design sheds)?
5. Trunk scaffold treatment in Phase 2: pure copy-exclude (recommended), or offer trunk repos the content-free emergency lane too?

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 08:15 AM_

## Implementation Plan

Issue: #1621
Branch: `feature/1621-hotfix-release-lane` (off `dev`, gitflow)
Scope: Phase 1 only — devkit's root workflows. Phase 2 (scaffold port) is a follow-up issue.

### Situation at planning time

- A regular train is in flight: `release/1.14.1` (PR #1620, draft, cut from `dev`, CI green). Highest stable tag on `main` is `1.14.0`.
- Consequence for testing: the new validate job will (correctly) refuse any hotfix until `1.14.1` promotes — another `release/*` exists, and `1.14.1` is the only valid patch number. Layer 1 dry-run positive cases and the Layer 2 rehearsal (`1.14.2`) wait for that promote; the negative dry-run cases can run immediately.
- `release.yml` executes from the release branch's copy, which for a hotfix is `main`'s copy. The finalize-time guard added here reaches hotfix trains only after it ships through a normal train (the next one after `1.14.1`).

### Decisions (open questions 1–5, plus implementation choices)

1. **Version policy: machine-enforced.** `version` must be `MAJOR.MINOR.(PATCH+1)` of the highest bare-semver tag reachable from `origin/main`. Anything else is refused with the expected value in the message.
2. **Concurrent trains: hard refuse.** Validate fails when any `release/*` branch exists. No override input (YAGNI); the operator abandons the other train first. This also retires runbook rule (i) for the prepare direction.
3. **`:latest` ordering: runbook only.** The promote guard widens the blast radius beyond the new file; filed as a follow-up issue.
4. **Dev-side changelog: manual sync conflict**, documented resolution recipe; the sync auto-resolver is not extended.
5. **Phase 2 trunk treatment: copy-exclude.** Recorded in the follow-up issue only.
6. **`prepare-changelog seed VERSION [FILE]`** — new subcommand that inserts an empty `## [VERSION] - TBD` directly under `## Unreleased`. It *refuses* a non-empty Unreleased and an existing `[VERSION]` section. (`prepare` would produce the same output on an empty Unreleased with only a warning, but the refusal is the hotfix invariant — `main`'s Unreleased is empty by construction, #590 — so a dedicated command makes the guard explicit.) Reuses `create_new_changelog(version, {}, rest)`.
7. **`prepare-changelog validate --version VERSION`** — validate gains an optional flag that checks `## [VERSION] - TBD` has content; `release.yml`'s "Verify CHANGELOG has TBD entry" step calls it. Applies to candidate and final alike (regular trains always have content there).
8. **Rollback = delete the partial branch only.** A PR exists only when `open-pr` succeeded, and then no rollback runs; deleting the branch closes a PR anyway. No `commit-action` step, no dev reads.
9. **Operator recipe** `just prepare-hotfix X.Y.Z [ref] [flags]` in `justfile.gh`, default dispatch ref `dev` (the workflow checks out `main` itself; the file reaches `main` only after a normal train, and `dev` matches `prepare-release`'s default). `justfile.gh` is manifest-synced into the consumer scaffold, so a `RemoveBlock` transform in `scripts/manifest.toml` strips the recipe from the scaffold copy until Phase 2.
10. **Zizmor**: CI audits only `assets/workspace/` workflows, so no baseline entry is needed in Phase 1. Every checkout in the new workflow sets `persist-credentials: false` (all writes go through the API) so the Phase 2 port adds nothing to `artipacked`.

### Workflow shape: `.github/workflows/prepare-hotfix.yml`

`workflow_dispatch` inputs `version`, `dry-run` (same names as `prepare-release.yml`). Top-level `permissions: contents: read`.

- **validate** (checkout `ref: main`, `fetch-depth: 0`, `persist-credentials: false`): semver format → highest stable tag on `main` + patch-increment check → no `release/*` branch exists (any) → no tag `X.Y.Z` → `## Unreleased` on `main` is empty (sanity, via `prepare-changelog validate` exit code) → summary. Outputs `version`, `release_branch`, `main_sha`.
- **prepare** (`if: dry-run != 'true'`; COMMIT_APP token; checkout `main`; setup-env): re-read `main` head via API and assert it equals `main_sha` (no race with a promote landing mid-run) → `POST git/refs` `release/X.Y.Z` at `main_sha` → verify resolvable → `prepare-changelog seed` locally → `vig-os/commit-action` with `TARGET_BRANCH: refs/heads/release/X.Y.Z`, `FILE_PATHS: CHANGELOG.md` → output `branch_sha` = the seed commit SHA (`commit-sha` output).
- **extension**: `uses: ./.github/workflows/prepare-release-extension.yml` with `branch_sha: needs.prepare.outputs.branch_sha`, `secrets: inherit`. Unchanged hook: its release-branch mirror sync commits (root gained a heading); the dev fast-forward branch is unreachable (`dev != branch_sha`); the fallback finds dev's mirror clean and no-ops.
- **open-pr** (RELEASE_APP token, bare shallow checkout of `main`): `gh pr create --base main --head release/X.Y.Z --draft --title "chore: release X.Y.Z"`, body: hotfix header, base SHA, and the instruction that the fix PR (`bugfix/N-*` → `release/X.Y.Z`) must fill `## [X.Y.Z] - TBD`. Summary prints the next steps (fix PR, `just publish-candidate`, `just finalize-release`, promote, expect a `CHANGELOG.md` conflict in the sync PR).
- **rollback** (`always()` + dry-run guard + `needs.validate.result == 'success'` + any of prepare/extension/open-pr failed or cancelled; COMMIT_APP token): delete `refs/heads/release/X.Y.Z` if present; summary.

### Tasks

Each numbered task is one commit (TDD: test commit, then implementation commit). `Refs: #1621` on every commit.

**A. Changelog tooling (`packages/vig-utils`)**

- [ ] 1. `test:` add `TestSeedChangelog` to `packages/vig-utils/tests/test_prepare_changelog.py` — inserts empty `[X.Y.Z] - TBD` under an empty Unreleased and keeps the rest byte-identical; refuses non-empty Unreleased; refuses an existing `[X.Y.Z]` section (TBD or dated); refuses a bad semver; missing file. — verify: `just test-vig-utils` RED on the new class only.
- [ ] 2. `feat:` `seed_changelog()` + `cmd_seed` + `seed` subparser in `packages/vig-utils/src/vig_utils/prepare_changelog.py`. — verify: `just test-vig-utils` GREEN.
- [ ] 3. `test:` add `TestValidateVersionSection` — `validate --version` passes with a bullet in any subsection, fails on an empty section, a missing section, or an already-dated heading; plain `validate` behavior unchanged. — verify: RED.
- [ ] 4. `feat:` `validate_version_section()` + `--version` flag on `validate` (reuse `_pop_version_section`/`_parse_subsections`). — verify: GREEN.

**B. Workflows**

- [ ] 5. `test:` new `tests/test_workflow_prepare_hotfix.py` (helpers from `tests/workflow_scaffold.py`), pinning: dispatch inputs `version`/`dry-run`; no checkout `ref: dev`, no `refs/heads/dev`, no `heads/dev` in any `run:` (grep over the whole file); branch-creating job checks out `main`; every job except `validate` gated on `dry-run != 'true'`; extension called with `branch_sha` from `prepare`'s output; `gh pr create` has `--base main`, `--draft`; rollback is `always()`, watches `prepare`/`extension`/`open-pr`, deletes a `release/` ref, and contains no `vig-os/commit-action`; validate `run:` text contains the patch-increment check and the `release/*` refusal; every checkout has `persist-credentials: false`; `release.yml`'s TBD step calls `prepare-changelog validate --version`; scaffold `assets/workspace/.devcontainer/justfile.gh` does NOT contain `prepare-hotfix` (Phase 1 leak guard). Add `DEVKIT_HOTFIX` to `CALLER_WORKFLOWS` in `tests/test_workflow_prepare_extension.py` so the branch→extension→PR DAG pin applies. — verify: `uv run pytest tests/test_workflow_prepare_hotfix.py tests/test_workflow_prepare_extension.py` RED (file missing).
- [ ] 6. `feat:` `.github/workflows/prepare-hotfix.yml` per the shape above. — verify: the two files above GREEN; `uv run pytest tests/test_scaffold_lint.py tests/test_workflow_model.py tests/test_ci_concurrency.py`; `prek run actionlint yamllint --files .github/workflows/prepare-hotfix.yml`.
- [ ] 7. `feat:` `release.yml` validate: replace the `grep` in "Verify CHANGELOG has TBD entry" with `uv run prepare-changelog validate --version "$VERSION" CHANGELOG.md` (step runs after setup-env; move if needed). — verify: task-5 assertion GREEN; `uv run pytest tests/test_release_validate_gate.py tests/test_release_core.py`.

**C. Operator surface**

- [ ] 8. `feat:` `prepare-hotfix version ref="" *flags` recipe in `justfile.gh` (group `release`, default ref `dev`) + `RemoveBlock` transform for it in `scripts/manifest.toml` (`justfile.gh` entry) + `uv run python scripts/sync_manifest.py sync assets/workspace/` (scaffold copy must stay byte-identical). Update the release process comment block in `justfile` to list the hotfix entry point. — verify: `just --list | grep prepare-hotfix`; task-5 leak guard GREEN; `prek run sync-manifest --all-files`.

**D. Docs and changelog**

- [ ] 9. `docs:` `docs/RELEASE_CYCLE.md` — branch-hierarchy mermaid (`main -->|"fork (hotfix)"| release`), branch table (`release` base: `dev`, or `main` for hotfixes), lifecycle note, new **Hotfix lane** section under Detailed Release Steps: when to use it vs an expedited regular train, `just prepare-hotfix`, what the workflow does, the fix PR contract (fills the seeded section), the unchanged candidate/final/promote path, runbook rules (ii) `:latest` walks backwards if a higher train promoted meanwhile, (iii) the promote BEHIND gate recovery (#1474), the `sync-main-to-dev` conflict recipe (keep dev's `## Unreleased` + bullets, insert main's dated `[X.Y.Z]` beneath, rerun `sync_manifest.py sync`, hook green, push), and the release.yml-copy caveat; Scripts and Tools: `seed`, `validate --version`; Justfile Recipes: `prepare-hotfix`; Troubleshooting: the expected changelog conflict. — verify: `prek run --files docs/RELEASE_CYCLE.md` (markdown hooks).
- [ ] 10. `docs:` `CHANGELOG.md` `## Unreleased` → `### Added` — **Hotfix release lane** ([#1621]) with sub-bullets (new workflow, `seed`/`validate --version`, finalize guard, `just prepare-hotfix`, accepted sync-conflict cost, Phase 2 pointer). Mirror regenerates via the sync-manifest hook. — verify: `prek run --all-files` green.

**E. Verification and delivery**

- [ ] 11. Full suite: `just precommit` green in the working tree (read the output), `just test-vig-utils`, `uv run pytest tests -k "workflow or release or scaffold"`.
- [ ] 12. Layer 1 (from the feature branch, side-effect free): `gh workflow run prepare-hotfix.yml --ref feature/1621-hotfix-release-lane -f version=V -f dry-run=true`. Now: `1.14.1` → refused (tag/branch exists), `1.14.2` → refused (another `release/*` exists; also not patch-of-latest), `1.15.0` → refused (not a patch). After `1.14.1` promotes: `1.14.2` → validate passes, no mutating job runs (check the run's job list). Record run URLs in the PR.
- [ ] 13. PR to `dev` (`/pr_create`), CI green, merge.
- [ ] 14. Layer 2 rehearsal (after merge, after `1.14.1` promotes, no train in flight): real `just prepare-hotfix 1.14.2` → assert branch forked at `main`'s SHA, draft PR base `main`, `dev` untouched (SHA before == after); trivial `bugfix/N-*` PR filling the section; CI green; `just publish-candidate 1.14.2`; then `just abandon-release 1.14.2`. Never finalize, never promote. Accepted leftovers: `1.14.2-rc1` git tag in devkit, one permanent published pre-release `1.14.2-rc1` on `devkit-smoke-test`, and if `1.15.0` ships before a real `1.14.2`, the rc tag stays orphaned (deletable by hand, no Release linked). Post the checklist result on #1621.

### Follow-up issues to file (not in this PR)

- Phase 2: port `prepare-hotfix.yml` to `assets/workspace/` — copy-exclude under `DEVKIT_WORKFLOW=trunk`, add to the `release` feature group, drop the `justfile.gh` `RemoveBlock` transform, add `github-app` (and `artipacked` if any) baseline entries for the managed basename, validate on `devkit-smoke-test`.
- `promote-release.yml`: semver guard refusing to move `:latest` backwards.
- `prepare-release.yml`: symmetric refusal when a `release/*` branch already exists (today nothing stops a normal train being cut while a hotfix is in flight, which is the scenario behind runbook rule (i)).


