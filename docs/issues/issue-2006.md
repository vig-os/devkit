---
type: issue
state: open
created: 2026-11-03T10:49:02Z
updated: 2026-11-03T10:49:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2006
comments: 0
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:57.776Z
---

# [Issue 2006]: [[FEATURE] Self-run security profile for private repos without GHAS (semgrep, zizmor, osv-scanner, gitleaks) + semgrep findings in managed workflows](https://github.com/vig-os/devkit/issues/2006)

## Description

Two related points from `exoma-ch/ravmatic` (private, Free org, devkit 1.18.0, direnv):

1. **An opt-in, self-run security profile** for repos where `scanning` (CodeQL, Scorecard) and Dependency Review can't run. That's private repos without GHAS (see #1997, #1913).
2. **semgrep `p/github-actions` findings in devkit-managed workflows.** Consumers can't fix these locally, because an edit fails scaffold drift.

## 1. Self-run security profile

On a Free-plan private repo, today's `scanning` group is inert and Dependency Review is skipped. ravmatic replaced them with tools that are already in the pinned nixpkgs, so they run identically locally and in CI with no container (https://github.com/exoma-ch/ravmatic/pull/12):

| Replaces | Tool |
|---|---|
| CodeQL | ruff `extend-select = ["S"]` (Bandit) in the hooks, plus `semgrep scan --config p/python --config p/github-actions --metrics=off --error` |
| workflow audit | `zizmor --offline .github/workflows` (devkit ships `zizmor.yml` but not the tool to consumers) |
| Dependency Review | `osv-scanner scan source -L uv.lock` (or the npm/cargo locks) |
| secret scanning | `gitleaks git --redact` over the full history (gitleaks is already in the toolchain) |

These are wired as `just security` plus a blocking job in `ci-extension.yml`. The semgrep step excludes every file headed `# Managed by vigOS devkit`, computed at run time so the exclude list never drifts.

On licensing: the CodeQL CLI in nixpkgs is free only for open-source and academic code. That's why this profile avoids it on private repos.

**Proposal:** a capability module plus feature group, e.g. `DEVKIT_MODULES="security"` and `security-local` in place of `scanning`. It would add these packages to the dev shell, render the recipe and CI job language-aware (only the lockfiles of `DEVKIT_LANGUAGES`), and be suggested automatically when the plan-aware check (#1997) finds a private repo without GHAS.

## 2. Findings in managed workflows (semgrep 1.172, `p/github-actions`)

| File (1.18.0 scaffold) | Rule | Lines |
|---|---|---|
| `release.yml` | `secrets-inherit` | 98, 124, 146 |
| `prepare-release.yml` | `secrets-inherit` | 437 |
| `prepare-hotfix.yml` | `secrets-inherit` | 438 |
| `ci.yml` | `secrets-inherit` | 656 |
| `devkit-upgrade.yml` | `gha-curl-pipe-shell` | 229 |

`secrets: inherit` hands every repo secret to the reusable workflow. Passing the specific App secrets each callee needs (`RELEASE_APP_*`, `COMMIT_APP_*`) would satisfy least privilege. That's especially relevant on Free-plan private repos, where the App keys must exist as repo-level secrets (#2004). If inheritance is deliberate (extension hooks receiving consumer secrets), a documented `nosemgrep` with the reason would let consumers keep the rule on. zizmor 1.25 reports no findings on the same files with the shipped `zizmor.yml`.

