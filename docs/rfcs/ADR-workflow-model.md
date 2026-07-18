---
rfc: ADR-workflow-model
date: 2026-07-18
title: Per-consumer workflow model — scaffold-time dev→main render, composed with delivery mode
status: accepted
authors:
- Carlos Vigo (c-vigo)
---

# ADR: Per-consumer workflow model (`gitflow` | `trunk`)

**Decision (TL;DR):** Realize the `DEVKIT_WORKFLOW` branching model
([#1205](https://github.com/vig-os/devkit/issues/1205)) **entirely at scaffold
time**, mirroring `DEVKIT_MODE`. `init-workspace.sh render_workflow_model` applies
an **anchored `dev -> main` retarget** to the already-copied workflows,
branch-naming skill, and pre-commit branch guard, and `sync-main-to-dev.yml` is
removed by a copy-exclude (plus an upgrade prune). `gitflow` (the default) is a
provable **byte-for-byte no-op**. Two alternatives are **rejected**: resolving the
model at **runtime** in `resolve-toolchain` (would leave an inert, perpetually
green `sync-main-to-dev` firing on every push to `main`), and shipping a **full
second copy** of each workflow as a `trunk` twin (the #1095 whole-file-overlay
drift class). The two orthogonal axes `mode × model` are **composed, not
combined**: separate sequential scaffold blocks, never a combined `case`.

## Problem statement

Consumers scaffolded from `assets/workspace/` run a **gitflow** branching model: a
long-lived `dev` integration branch, `release/X.Y.Z` cut from `dev`, finalize
merging to `main` + tag, and `sync-main-to-dev.yml` back-merging `main` into
`dev`. Some consumers want a **trunk** model instead — `feature`/`bugfix`/`chore`
branches straight to `main`, no `dev`, no back-merge — while keeping the **entire**
downstream tag/build/publish/promote train, which already runs `release/* → main`.

The two models differ **only** in branch topology: under `trunk` the release
branch forks from `main` and merges back into `main`, and the `dev` branch plus
`sync-main-to-dev.yml` disappear. Nothing in the release *choreography* (step
logic, ordering, `workflow_call` inputs/outputs, rollback) changes. The question
is **how** to express that topology difference in the scaffolded artifacts without
re-plumbing the release pipeline or growing a drift-prone parallel copy — and how
it composes with the existing per-mode (`DEVKIT_MODE`) scaffold.

The **enabling fact:** in `prepare-release.yml`, every reference to `dev` that
drives behavior is a **plain branch literal** — checkout `ref: dev`, REST
`heads/dev` reads, and `… from dev` targets — never a computed value or a
structural dependency. The `#590/#617` release-preparation logic is
**base-agnostic**: it freezes the changelog on the base branch and forks the
release branch from it, whatever that base is. So retargeting the base is a
**literal substitution**, not a rewrite. (The remaining `dev` spellings —
`/dev/null`, the `dev_sha`/`DEV_SHA` variable names — are inert and deliberately
preserved.)

## Decision

### (a) Scaffold-time render, not runtime and not a workflow twin

`render_workflow_model "$WORKFLOW_MODEL"` runs **after** the `rsync` copy (a
sibling of `render_codeql_matrix`) and, for `trunk` only, applies **anchored**
`sed` substitutions to the copied files:

- **`prepare-release.yml`** — behavioral branch literals `ref: dev → ref: main`,
  `heads/dev → heads/main`, `… from dev → … from main`; plus inert step-names and
  the `#590` sync-merge rationale comment reworded (no behavior change — the
  literals above drive the retarget).
- **`ci.yml`** — drop `- dev` from the PR branch filter; retarget the commit-gate
  `TRUNK="dev" → "main"` anchor.
- **`codeql.yml`** / **`sync-issues.yml`** — drop `- dev` from the PR filter;
  retarget the sync-issues default branch and `|| 'dev'` fallbacks.
- **branch-naming `SKILL.md`** — base-branch default `dev → main`.
- **`.pre-commit-config.yaml`** — drop the `(?!dev$)` protect-clause (`main` stays
  protected; `trunk` has no long-lived `dev` to protect).

Anchoring is load-bearing: `heads/dev\b` (word boundary) never touches
`development`/`devkit`/`devcontainer`; `ref: dev$` / `from dev$` are end-anchored.
`sync-main-to-dev.yml` is not edited here — it is removed by `EXCLUDE_ARGS` at copy
time and pruned on a `gitflow → trunk` upgrade.

Because the substitutions only fire for `trunk`, a `gitflow` scaffold is
**byte-for-byte identical** to today, and `.vig-os` is written back only for
`trunk` — existing consumers are untouched.

**Rejected — runtime resolution in `resolve-toolchain`.** The mode axis is already
resolved at runtime (an `image` output); the tempting symmetry is to resolve the
model there too and gate release steps on it. But the topology is not a runtime
property of a single workflow run — it is which *branches and workflow files
exist*. A runtime approach cannot make `sync-main-to-dev.yml` *not exist*: the
best it can do is ship the workflow and no-op its body under `trunk`, leaving an
**inert, perpetually green `sync-main-to-dev` run firing on every push to `main`** —
misleading noise, a standing "why is this here?" question, and a permanent
maintenance surface for a workflow that should simply be absent. Topology belongs
to scaffold time.

**Rejected — a full-file `trunk` workflow twin.** Shipping a second copy of each
workflow (a `assets/workspace-trunk/` overlay, or committed `*-trunk.yml` files)
is the **#1095 whole-file-overlay drift class**: every future edit to a release
workflow must be mirrored into its twin by hand, and the two silently diverge the
first time someone forgets. The anchored render derives the `trunk` variant from
the **one** maintained `gitflow` source, so there is exactly one file to edit and
no twin to keep in sync.

### (b) Compose the `mode × model` axes, don't combine them

`DEVKIT_MODE` and `DEVKIT_WORKFLOW` are **orthogonal** — any of the four modes can
run either model. They are applied as **separate, sequential scaffold blocks** (the
mode filters/overlays run, then `render_workflow_model` runs on the result), never
folded into a single combined `case "$MODE/$WORKFLOW"`. A combined matrix would be
`4 × 2 = 8` cases to enumerate and test, most of them redundant, and would couple
two decisions that have nothing to do with each other. Composition keeps each axis
independently readable, independently testable, and additive: a future third axis
slots in as another sequential block rather than multiplying the matrix.

## Consequences

- **`gitflow` is a no-op.** The render returns early unless `model == trunk`;
  existing consumers, their `.vig-os`, and this repository are unchanged. This is
  the property that makes the feature safe to ship without a migration.
- **Switching is destructive and guarded.** The scaffold renders files but cannot
  reshape branch topology. An explicit `--workflow` contradicting the persisted
  `DEVKIT_WORKFLOW` **refuses** (mirroring the `DEVKIT_MODE` contradiction guard);
  `--preview` inspects first. A `gitflow → trunk` switch leaves an **orphan remote
  `dev` branch** to delete manually — the scaffold must not delete branches. See
  [`docs/MIGRATION.md`](../MIGRATION.md#workflow-models).
- **Anchoring is a maintenance contract.** New `dev` references added to
  `prepare-release.yml` (or the other rendered files) must stay plain branch
  literals for the retarget to keep working; a computed `dev` base would break the
  literal-substitution assumption. The per-model rendered-workflow test assertions
  guard this.
- **Downstream train unchanged.** The tag/build/publish/promote chain already runs
  `release/* → main`, so it is model-agnostic; only the release-branch *base* and
  the presence of `sync-main-to-dev.yml` differ. See
  [`docs/DOWNSTREAM_RELEASE.md`](../DOWNSTREAM_RELEASE.md#workflow-models).
- **No repo-settings dependency.** Like the mode work, this is pure scaffold +
  workflow YAML and needs no branch-protection features (the orgs are on GitHub
  Free); topology hygiene (default branch, protection rules) is a documented manual
  step on a switch.

## References

- Epic [#1205](https://github.com/vig-os/devkit/issues/1205); sub-issues
  [#1206](https://github.com/vig-os/devkit/issues/1206)–[#1211](https://github.com/vig-os/devkit/issues/1211);
  plan `docs/plans/2026-07-18-workflow-model-plan.md`.
- Precedent: `docs/rfcs/ADR-conditional-container-toolchain.md` and
  `docs/plans/2026-07-13-mode-aware-scaffold-plan.md` (the `DEVKIT_MODE` scaffold-
  time model this mirrors; the #1095 whole-file-overlay drift class it avoids).
- As-built render: `assets/init-workspace.sh` (`render_workflow_model`), the
  `sync-main-to-dev.yml` copy-exclude/upgrade-prune, and the `install.sh`
  dev-branch gate.
- Topology and consumer docs: `docs/RELEASE_CYCLE.md` (Workflow models),
  `docs/MIGRATION.md` (Workflow models), `docs/DOWNSTREAM_RELEASE.md` (Workflow
  models).
