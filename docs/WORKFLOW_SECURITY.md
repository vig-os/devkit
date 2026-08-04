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

## Dependency maintenance for managed files (Renovate)

The managed workflows and the two managed composite actions
(`.github/actions/setup-devkit-toolchain`, `.github/actions/resolve-toolchain`)
carry SHA-pinned third-party `uses:`. Because these files are devkit-owned and
regenerated wholesale on every `devkit-upgrade`, **their dependency maintenance
sits upstream in devkit, not in the consumer.** Devkit's own Renovate advances
the digests and ships them with each release; the consumer picks them up on the
next upgrade.

To stop consumers from opening duplicate pin-bump PRs against files the next
upgrade clobbers, the shipped preset
([`assets/workspace/.github/renovate-default.json`](../assets/workspace/.github/renovate-default.json))
ends with an `enabled: false` `packageRule` naming exactly the managed set (all
shipped workflows **minus** the consumer-owned seams `release-extension.yml` and
`prepare-release-extension.yml`, plus the two managed action directories). The
enumeration is drift-gated by
[`tests/test_renovate_preset_managed_exclusion.py`](../tests/test_renovate_preset_managed_exclusion.py)
so a new or renamed managed workflow cannot silently reopen the gap.

Accepted trade-off: disabling updates for managed files also suppresses
Renovate's vulnerability PRs for those pins downstream. This is consistent with
the doctrine that devkit is the patch channel for managed files — an emergency
hand-bump downstream still works, and the next upgrade re-converges.

**Opting back in.** The exclusion is the *last* rule in the preset, so a
consumer's own later `packageRules` win. A consumer that deliberately wants to
manage a specific managed file adds a re-enabling rule to its preserved root
`renovate.json`, for example:

```json
{
  "packageRules": [
    {
      "description": "Manage pins in this workflow locally despite the devkit preset",
      "matchFileNames": [".github/workflows/ci.yml"],
      "enabled": true
    }
  ]
}
```

Devkit itself uses exactly this mechanism: it extends the same preset, so its
root `renovate.json` re-enables `.github/workflows/**` and `.github/actions/**`
to keep advancing the pins it owns (the shipped copies under `assets/workspace/`
are unaffected — the preset's rooted `matchFileNames` globs do not match nested
paths).
