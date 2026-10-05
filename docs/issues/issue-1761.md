---
type: issue
state: closed
created: 2026-09-29T08:27:15Z
updated: 2026-10-01T13:20:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1761
comments: 3
labels: feature, area:ci, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:25.520Z
---

# [Issue 1761]: [CI Summary cannot gate on jobs outside the managed ci.yml — consumers need a way to feed extra jobs into the aggregator](https://github.com/vig-os/devkit/issues/1761)

## Problem

The scaffolded `.github/workflows/ci.yml` is a managed file (regenerated on upgrade; local edits are lost). Its `summary` job — display name `CI Summary` — is the single required status check that vig-os/org-config's `Main` ruleset gates on for every tier-A repo (ADR-0008 in vig-os/org-config).

`summary.needs` is fixed to `ci.yml`'s own jobs:

```yaml
needs: [resolve-toolchain, lint, test, commit-checks, scaffold-drift, dependency-review]
```

A consumer that runs part of its CI in its own, non-managed workflow therefore has no way to make those jobs gate merges through `CI Summary`.

## Concrete case: vig-os/scitadel

scitadel's `.github/workflows/rust-ci.yml` runs:

- `Lint` — `cargo fmt --check` + `cargo clippy --workspace -- -D warnings`
- `Test (ubuntu-latest)` / `Test (macos-latest)` — a `cargo test --workspace` matrix

None of these can feed `CI Summary`, so with `CI Summary` as the only required check a red clippy or a failing macOS leg does not block a merge.

## Why the workarounds are not adopted

Both were evaluated under vig-os/org-config#294 and rejected (2026-09-29):

- **List the extra job names as additional required checks in org-config.** Required-check contexts are matched by name, so any job rename or matrix change silently breaks the gate (the check is never reported, or a new leg is never required). It also pushes per-repo CI layout into org config.
- **Bolt the tools onto the managed `lint` job via pre-commit hooks.** Slows every contributor's commit, and cannot cover a non-Linux leg such as `Test (macos-latest)`.

## Requirement

A supported, upgrade-safe way for a consumer repo to declare additional jobs — possibly defined in other workflow files — that `CI Summary` must wait on and fail with (same failure/cancelled semantics as the built-in jobs), so that a single required check keeps covering the repo's whole CI.

- Must survive `devkit-upgrade` without excluding `ci.yml` from upgrades or disabling the drift check.
- Consumers that declare nothing must be unaffected.

Design is left to devkit.

## Context

- Org-wide merge-protection audit: vig-os/org-config#294 (ADR-0008 tiers)
- Related downstream: vig-os/scitadel#227 (required-check set for scitadel's rulesets)

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 12:42 PM_

## Proposed design

Add a third preserved `workflow_call` extension seam — `ci-extension.yml` — following the exact shape already proven by `release-extension.yml`/`prepare-release-extension.yml`: a consumer-owned, upgrade-safe stub, no-op by default, called by managed `ci.yml` as a job named `extension`. Gate the call itself behind a new boolean `.vig-os` knob, `DEVKIT_CI_EXTENSION` (default `false`, same pattern as `DEVKIT_DRIFT_CHECK`), resolved by `resolve-toolchain` into a job output and consumed by the `extension` job's `if:`. When the knob is unset, the job is **skipped before a runner is even allocated** — zero cost for the ~every consumer that declares nothing, no content-sniffing needed. `summary.needs` gains `extension` unconditionally (skip is already a tolerated result there, same as `scaffold-drift`/`dependency-review`); a `failure`/`cancelled` result trips the gate exactly like the other five jobs. The required check stays `CI Summary` — no org-config change, no per-repo job name ever enters a ruleset.

### Options

| Option | Verdict |
|---|---|
| **(a) Preserved `ci-extension.yml` stub, called by managed `ci.yml`, gated by `DEVKIT_CI_EXTENSION`** | **Recommended.** Reuses the exact extension-seam pattern already shipped twice; matrix/macOS "just works" because a reusable-workflow-call job's result already aggregates every job inside it; permissions ceiling, `secrets: inherit`, and skip-is-OK semantics all have direct precedent in `ci.yml`/`release.yml`. |
| (b) `.vig-os` knob listing external check names, `summary` polls the Checks API | Rejected. Same failure mode #294 already rejected for org-config: exact-name matching breaks silently on a job/matrix rename. Needs `checks: read`, polling/timeout logic, and still can't give the external job devkit's toolchain/runner outputs. |
| (c) Consumer authors its own aggregator job, required check moves off `CI Summary` | Rejected. Breaks the "`CI Summary` stays the single required context" invariant ADR-0008 relies on; re-implements cancelled/failure semantics per consumer instead of once in devkit. |

### Shape

`assets/workspace/.github/workflows/ci.yml` (managed) — insert after `dependency-review`, before `summary`:

```yaml
  extension:
    name: CI Extension
    needs: [resolve-toolchain]
    if: needs.resolve-toolchain.outputs.ci-extension == 'true'
    uses: ./.github/workflows/ci-extension.yml
    permissions:
      contents: read
      packages: read
    with:
      mode: ${{ needs.resolve-toolchain.outputs.mode }}
      image: ${{ needs.resolve-toolchain.outputs.image }}
      image-tag: ${{ needs.resolve-toolchain.outputs.image-tag }}
      runner-json: ${{ needs.resolve-toolchain.outputs.runner-json }}
    secrets: inherit

  summary:
    needs: [resolve-toolchain, lint, test, commit-checks, scaffold-drift, dependency-review, extension]
    # + one more failure/cancelled block for needs.extension.result, same shape as scaffold-drift's
```

New preserved stub, `assets/workspace/.github/workflows/ci-extension.yml` (same banner/no-op pattern as `release-extension.yml`):

```yaml
on:
  workflow_call:
    inputs:
      mode: { required: true, type: string }
      image: { required: true, type: string }
      image-tag: { required: true, type: string }
      runner-json: { required: true, type: string }
permissions:
  contents: read
jobs:
  extension:
    name: Extension Hook (Default No-op)
    runs-on: ubuntu-26.04
    steps:
      - run: echo "No CI extension configured."
```

`resolve-toolchain` action gains a `ci-extension` output (reads `.vig-os` `DEVKIT_CI_EXTENSION`, validated `true|false`, default `false` — mirrors `drift-check`).

### Files to touch

- `assets/workspace/.github/workflows/ci.yml` — `extension` job + `summary` wiring
- `assets/workspace/.github/workflows/ci-extension.yml` — new preserved stub
- `assets/workspace/.github/actions/resolve-toolchain/action.yml` — `ci-extension` output
- `assets/init-workspace.sh` — `PRESERVE_FILES` entry (comment: "same preserved class as release-extension.yml"), `DEVKIT_CI_EXTENSION` read/validate/round-trip (mirrors the `DEVKIT_DRIFT_CHECK` block), docs string updates
- `docs/DOWNSTREAM_RELEASE.md` or a new CI doc section — document the seam, token-ceiling note like the release extensions carry
- `CHANGELOG.md` `## Unreleased`

### Test plan (TDD order)

1. `tests/test_transforms.py` / banner-variant test — `ci-extension.yml` classified as preserved, correct banner (red first: assert preserved-class membership, fails until `PRESERVE_FILES` updated).
2. `assets/init-workspace.sh` — knob validation test (invalid `DEVKIT_CI_EXTENSION` value errors; round-trips like `DEVKIT_DRIFT_CHECK`) — likely a bats fixture alongside the existing drift-check one.
3. `resolve-toolchain` action test — `ci-extension` output resolves default `false` and an explicit `true`.
4. `tests/test_workflow_*` (mirroring `test_workflow_release_extension.py`) — `ci.yml`'s `extension` job exists, is gated correctly, and `summary.needs` includes it with the matching failure/cancelled block.
5. Scaffold/upgrade test — a repo with a hand-edited `ci-extension.yml` survives `--force` untouched; a fresh scaffold seeds the no-op stub.

### Migration note (scitadel)

Move `rust-ci.yml`'s `Lint` (clippy `-D warnings`) and `Test (ubuntu-latest)`/`Test (macos-latest)` matrix into jobs inside `ci-extension.yml`, set `DEVKIT_CI_EXTENSION=true` in `.vig-os`, delete `rust-ci.yml`. Once this ships, vig-os/org-config#294's deferred row (clippy + macOS gating `CI Summary`) closes by re-pointing scitadel's rulesets at nothing extra — `CI Summary` already covers it.

### Open questions for the maintainer

1. Should the `extension` job's permissions ceiling match `ci.yml`'s current top-level (`contents: read, packages: read`), or does a known consumer need more (e.g. `id-token: write` for a coverage upload) — same ceiling-vs-need question `release.yml` answers with a wider grant?
2. Is `DEVKIT_CI_EXTENSION` the right knob name/default, or should presence of a non-stub `ci-extension.yml` alone be enough to opt in (trading the explicit knob for content-sniffing, which the skip-cost analysis above argues against)?

Awaiting maintainer approval before implementation.


---

# [Comment #2]() by [c-vigo]()

_Posted on October 1, 2026 at 12:46 PM_

## Design approved, with four amendments

The seam in the proposal above is approved: a preserved `ci-extension.yml` `workflow_call` stub called from managed `ci.yml` as `extension`, judged by `CI Summary`. These four changes apply:

1. **No `DEVKIT_CI_EXTENSION` knob — always call the extension.** A knob reintroduces the failure this issue exists to prevent: a consumer writes real jobs into `ci-extension.yml`, forgets the knob, the job is silently skipped and red clippy merges again. The no-op costs one tiny runner per PR, and the release extensions are always called too. No `resolve-toolchain` output change is needed.
2. **Every `workflow_call` input is `required: false`.** The stub is a preserved, consumer-owned contract; a later devkit release adding a required input would break every consumer's copy. Optional inputs let devkit add inputs without breaking anyone.
3. **The stub takes its runner from `runner-json` (`fromJSON`), never a literal `runs-on: ubuntu-26.04`.** actionlint 1.7.12 does not know the `ubuntu-26.04` label, so a literal label fails consumers' lint the moment they start editing the stub.
4. **smoke-test gets a real (non-empty) extension**, so the seam is live-proven by the release train and scitadel's migration is not its first test.

Permissions ceiling stays read-only (`contents: read`, `packages: read`); no consumer needs more today.


---

# [Comment #3]() by [c-vigo]()

_Posted on October 1, 2026 at 01:20 PM_

Shipped on `dev` in #1797: the managed `ci.yml` now always calls a preserved, consumer-owned `.github/workflows/ci-extension.yml` (seeded as a no-op; upgrades add it when absent and never overwrite it), and `CI Summary` fails on its `failure`/`cancelled`. `CI Summary` stays the single required check. Built to the approved amendments (no knob, optional inputs, runner from `runner-json`, a real smoke-test extension that the release train exercises). Documented under *CI Extension Hook* in `docs/DOWNSTREAM_RELEASE.md`. Reaches consumers with the next release; vig-os/scitadel can then fold `rust-ci.yml`'s clippy + ubuntu/macOS matrix into it (vig-os/scitadel#227, vig-os/org-config#294).

