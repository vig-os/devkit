# Managed Workflow Security (zizmor)

This document describes how devkit audits the GitHub Actions workflows it
generates for consumers, and the policy behind the shipped
[`zizmor`](https://docs.zizmor.sh) baseline (`zizmor.yml`).

## Problem

Every consumer scaffolded by devkit receives ~14 managed workflows
(`assets/workspace/.github/workflows/`) whose header banners say they are
regenerated on upgrade. A consumer that adopts workflow security linting cannot
fix findings in that generated code — it does not own it — so without a
devkit-supplied baseline each consumer has to maintain its own exemption list
for devkit's output, re-triaging it on every upgrade (#1182).

## Policy

1. **Fix upstream what is fixable, without changing behavior.** These workflows
   run releases and CI for every consumer, so fixes are surgical and
   behavior-preserving:
   - **`persist-credentials: false`** on checkouts that only read the tree (CI
     lint/test, toolchain resolution, CodeQL, dependency review) — they never
     push or fetch from the remote, so dropping the persisted git credential is
     inert. Checkouts that push or fetch from a (possibly private) remote keep
     the credential.
   - **Untrusted `${{ … }}` interpolations move into `env:`** so a step body
     cannot be templated into by expansion context.
   - **`uses:` are SHA-pinned** with a trailing `# vX.Y.Z` comment; Renovate's
     `github-actions` manager keeps the digests fresh.
2. **Baseline the intentional remainder — devkit owns it.** `zizmor.yml` (repo
   root) is the single source of truth. It suppresses only the residual findings
   that cannot be fixed without changing release/CI behavior:
   | Audit | Why it is intentional |
   |-------|-----------------------|
   | `artipacked` | The checkout pushes or fetches from a private remote and needs the persisted credential (release/sync branch work, the CI commit-checks base-diff). |
   | `dangerous-triggers` | `renovate-changelog-commit.yml` runs on `workflow_run` by design to commit the built changelog. |
   | `github-app` | `create-github-app-token` mints a broadly-scoped installation token for multi-repo release orchestration; per-permission scoping would break those flows. |
   | `secrets-inherit` | `release.yml` / `prepare-release.yml` fan out to reusable workflows with `secrets: inherit` by design. |
   | `unpinned-images` | `image:` is the devkit toolchain image resolved at runtime; it cannot be SHA-pinned in source. |
3. **Consumers inherit the baseline; their own baseline shrinks to zero.**
   `zizmor.yml` is a scaffolded/managed asset (registered in
   `scripts/manifest.toml`), so a consumer adopting `zizmor` gets exactly
   devkit's exemptions and maintains none of its own for managed files.
4. **A repo-authored workflow never inherits an exemption.** Every baseline
   entry is a specific managed-workflow **basename** (e.g. `release.yml`), never
   a `*.yml` glob. A consumer's own workflow has a different filename, so its
   findings are always reported. This scope rule is enforced by
   `tests/test_workflow_zizmor_baseline.py`.

## Regression gate

Devkit's own CI (`.github/workflows/ci.yml`, `project-checks` job) runs

```
uvx zizmor@<pinned> --offline --config zizmor.yml assets/workspace/.github/workflows/
```

so the managed set must report **zero** unbaselined findings. A new zizmor
audit, a new/renamed managed workflow, or a managed workflow that regains a
fixed finding fails devkit CI — it must be fixed in the workflow or triaged into
`zizmor.yml` as part of that change, never left for consumers to absorb.

## Maintenance

When a devkit upgrade adds, renames, or removes a managed workflow, or a new
zizmor audit surfaces, update `zizmor.yml` (or fix the workflow) in the same PR.
The zizmor version in the CI gate is pinned deliberately: a floating version
would let a newly-released audit break CI unpredictably, so version bumps are an
explicit, reviewed change that re-baselines any new findings at the same time.
