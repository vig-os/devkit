# Plan: Per-consumer workflow model — `DEVKIT_WORKFLOW` (gitflow | trunk)

**Issue**: #1205 (sub-issues #1206–#1211)
**Date**: 2026-07-18
**Design decision**: Realize the branching model **entirely at scaffold time**,
mirroring `DEVKIT_MODE` — an anchored `dev -> main` render of the copied
workflows/skill/pre-commit guard plus a `sync-main-to-dev.yml` copy-exclude — not
via runtime workflow logic and not a full-file workflow twin. Recorded as
[`docs/rfcs/ADR-workflow-model.md`](../rfcs/ADR-workflow-model.md).

---

## Scope

Add an optional `.vig-os` key `DEVKIT_WORKFLOW` (and `--workflow gitflow|trunk`
flag on `install.sh`/`init-workspace.sh`) that selects a consumer's branching
model. Empty/absent resolves to the unchanged **gitflow** default. `trunk` opts a
repo into a trunk-based flow:

- **gitflow (default):** long-lived `dev` integration branch; `release/X.Y.Z` cut
  from `dev`; RC train; finalize merges to `main` + tag; `sync-main-to-dev.yml`
  back-merges `main` into `dev`.
- **trunk:** `feature`/`bugfix`/`chore` branches straight to `main`. Releases are
  otherwise unchanged — `release/X.Y.Z` cut **from `main`**, same
  RC/vulnix-gate/promote train, **merged back into `main`** + tag. The **only**
  things that disappear are the `dev` branch and `sync-main-to-dev.yml`; the whole
  downstream tag/build/publish/promote chain is untouched (already `release/* →
  main`).

Out of scope: any change to the release choreography (step logic, ordering,
`workflow_call` I/O, rollback) and any repo-settings automation.

## Key findings from the spike (#1206)

- **Every `dev` reference in `prepare-release.yml` that drives behavior is a plain
  branch literal** (`ref: dev`, `heads/dev`, `… from dev`); the `#590/#617`
  release-prep logic is base-agnostic. Retargeting the base is therefore a
  **literal substitution**, not a rewrite — this is the enabling fact for the
  anchored render.
- The remaining `dev` spellings (`/dev/null`, `dev_sha`/`DEV_SHA`) are inert and
  must be preserved; anchoring (`heads/dev\b`, end-anchored `ref: dev$` /
  `from dev$`) keeps `development`/`devkit`/`devcontainer` untouched.
- gitflow can be a **provable byte-for-byte no-op** (render returns early unless
  `model == trunk`), so the feature ships with no migration for existing
  consumers; `.vig-os` is written back only for `trunk`.

## Architecture

- **`render_workflow_model`** (`init-workspace.sh`), a sibling of
  `render_codeql_matrix`, runs **after** the `rsync` copy and applies anchored
  `sed` retargets to `prepare-release.yml`, `ci.yml`, `codeql.yml`,
  `sync-issues.yml`, the branch-naming `SKILL.md`, and `.pre-commit-config.yaml`
  for `trunk` only.
- **`sync-main-to-dev.yml`** is removed by `EXCLUDE_ARGS` at copy time and pruned
  on a `gitflow → trunk` upgrade; the `--force` preview and preview-only path
  report the render truthfully.
- **`install.sh`** forwards `--workflow`, guards the enum + the implicit-switch
  contradiction, and **gates off `dev`-branch creation** (and the `git push … dev`
  hint) for `trunk`.
- **Compose, don't combine:** the `mode` and `model` axes are applied as separate
  sequential scaffold blocks, never a combined `case`. See the ADR.

## Work breakdown

| Sub-issue | Task | Size |
|-----------|------|------|
| #1206 | Spike: prove trunk release cut-from-main + scaffold render | S |
| #1207 | `DEVKIT_WORKFLOW` manifest key + read/writeback + enum/contradiction guards | S |
| #1208 | Scaffold render core (`render_workflow_model` + `sync-main-to-dev` exclude/prune + preview mirror) | M |
| #1209 | `install.sh` `--workflow` flag + dev-branch creation gating | S |
| #1210 | Tests (`test_workflow_model.py` + bats render assertions + parametrize the dev-assuming suites) | M |
| #1211 | Docs + ADR + this plan | S |

Order: spike (#1206) → guards/manifest (#1207) + flag/gating (#1209) → render core
(#1208) → tests (#1210) → docs (#1211). Delivered on sibling branches into the
`feature/1205` line; docs land last against the as-built render.

## Execution mechanics

Sub-issue branches PR into the epic integration branch. TDD throughout: the render
core lands behind red/green bats + `test_workflow_model.py` assertions that pin the
anchored substitutions and the gitflow no-op, and the existing dev-assuming suites
are parametrized over both models so gitflow stays byte-for-byte identical. The
CHANGELOG `## Unreleased` `Added` entry is authored with the core commits; the docs
sub-issue aligns prose to it without duplicating.
