---
type: issue
state: closed
created: 2026-09-29T11:07:41Z
updated: 2026-10-01T17:46:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1762
comments: 1
labels: feature, priority:medium, area:ci, area:testing, effort:large
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:24.587Z
---

# [Issue 1762]: [feat(ci): run a rendered-consumer variant matrix in PR CI](https://github.com/vig-os/devkit/issues/1762)

### Description

Add a PR-CI job that scaffolds a matrix of consumer variants into temp directories and runs each rendered consumer's **own** gates, not just checks on what files were rendered.

### Problem Statement

The scaffold now has many variants: `DEVKIT_MODE` (devcontainer / direnv / both / bare), `DEVKIT_WORKFLOW` (gitflow / trunk), `DEVKIT_LANGUAGES` (python / node / rust / nix), `DEVKIT_FEATURES_DISABLED`, `DEVKIT_CI_RUNNER`, `DEVKIT_TAG_PREFIX`, and others. Coverage today:

- **bats (`init-workspace.bats`, ~300 tests)**: checks the *rendered files* (which files appear, anchored renders, knob round-trips). It never executes the rendered consumer.
- **`nix-image.yml`**: one `init-workspace.sh --no-prompts --mode both` render.
- **devkit-smoke-test**: exactly one live variant (gitflow, `--mode both`, Python), deployed only at release time, after publish.
- **The real consumers**: the first time any other combination is actually executed. That happens through `devkit-upgrade` adoption PRs, *after* promote.

So a variant that renders the right files but fails when it runs is first seen at RC time if it happens to be the smoke variant, or after release on a consumer otherwise. Earlier cases of that kind of gap: #1132 / #1487 (tests reading the scaffold copy), #1466 (a deleted Python project with `Tests` green), and the local-only insert-idempotence false pass seen on 1.17.0.

Throwaway branches in devkit-smoke-test are not the answer. Workflow model, default branch, rulesets and visibility are set on the repo, not the branch, and releases and tags are immutable org-wide (a deleted tag's name is permanently burned). Most render variants don't need GitHub at all.

### Proposed Solution

A `consumer-matrix` job in devkit PR CI. For each matrix cell:

1. Render with the PR's `assets/init-workspace.sh` into a temp workspace, using a minimal language fixture (zero-dependency hello world plus one test per language).
2. Run the rendered consumer's own gates: `just lint`, `just test`, `just precommit` (prek), a flake evaluation where the mode ships a flake, and actionlint/zizmor over the rendered `.github/workflows`.
3. Fail the job on any cell failure, and name the cell in the summary.

Pick matrix axes by what each one changes in the rendered output, not as a full cross product. For example:
- mode: direnv, devcontainer, bare (`both` is already live in smoke-test)
- workflow: gitflow, trunk
- language: one cell each for python, node, rust, plus a language-neutral cell (the #1466 guard: declared language with no marker must fail)
- a few knob cells: every feature disabled, a custom `DEVKIT_CI_RUNNER`, `DEVKIT_TAG_PREFIX=v`

Scope question to settle at design time: whether to reuse the RC validation recipe (a `just` stub plus `TEMPLATE_DIR` / `WORKSPACE_DIR` env) or run a real `just`/`uv`/`nix` in each cell, and what that costs in CI time (the critical path is currently about 5 min).

### Alternatives Considered

- **Throwaway `smoke/<variant>` branches in devkit-smoke-test with draft PRs.** They only cover PR-CI variants. They can't vary repo-level settings or the release lane, they run only after publish, and they cost live Actions runs and PR numbers. Rejected as the default.
- **A second smoke repo per workflow model (`devkit-smoke-test-trunk`).** This is the only way to prove the trunk *release lane* live before promote. Deferred: only worth adding if a trunk release bug gets through; the post-release consumer rollout covers it today.
- **Rely on the consumer rollout.** It happens after promote, so a variant bug reaches `:latest` first.

### Additional Context

This defines devkit-smoke-test's role as the **one standard consumer on live GitHub**: consuming the published artifacts, the scaffolded workflows under real Apps and rulesets, the full consumer release train, and the direnv install paths. It uses a minimal Python payload (vig-os/devkit-smoke-test#438). Language and setup variants belong in this matrix instead.

### Impact

Devkit CI only. No change to what consumers receive.

### Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 05:46 PM_

Resolved by #1803 and #1807 (merged to `dev`, ship with the next release): the `Consumer Matrix` PR-CI job renders 12 consumer variants with the PR's own `init-workspace.sh` and runs each one's own gates (lint, precommit, the first-commit hook run, actionlint, zizmor, the declared-language guard, `just test` for the python/node/rust fixtures, and a flake check). Cells live in `scripts/consumer-matrix/render-cell.sh`, which also runs any cell locally as the RC validation recipe. It adds nothing to the critical path. On its first run it caught #1800 and #1801. The `rust` cell is a strict expected-fail tracked on #1496.


