---
type: issue
state: closed
created: 2026-07-29T13:34:25Z
updated: 2026-07-30T08:54:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1296
comments: 1
labels: feature, priority:medium, area:workflow, effort:large, semver:minor
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T11:51:50.591Z
---

# [Issue 1296]: [feat(workflow): self-polling devkit-upgrade workflow (auto adoption PR in consumers)](https://github.com/vig-os/devkit/issues/1296)

### Description

Ship a managed `devkit-upgrade.yml` workflow into consumers (same channel as `ghcr-cleanup.yml` / sync workflows) that periodically checks for a newer devkit release and, when found, performs a full-fidelity upgrade and opens the adoption PR. Renovate-style pull — no involvement from the devkit repo at release time, no consumer registry, no change to devkit's release/promote workflows. Merging stays human. Opt-out via `.vig-os`, default enabled.

Depends on #1295 (scaffold-drift CI gate) landing first — it is the safety net every automated (and manual) bump merges against.

### Problem Statement

Every release train requires one adoption PR per consumer (currently 5), each hand-built; rc iterations multiply this (rc2→rc3 re-bumps ×5 in 1.4.1). It is the largest recurring manual cost per train and it is mechanical.

The upgrade is not a version-string edit: the `.vig-os` pin + the `flake.lock` `vigos` node (a SHA decoupled from the semver) + full scaffold regeneration must move together, and commits must run with hooks active (commit-action's hooks rebuild `dist/`; trailer strip + commit-msg validation only run inside container/nix-shell). Only the real `install.sh --force` path delivers all of this — hence a first-party workflow, not a bot config.

### Proposed Solution

**Triggers**

- `schedule`: weekly cron, aligned with the Renovate window (Monday early AM). Notes: scheduled workflows execute from the default branch (fine — the job checks out and targets the right base itself), and GitHub pauses cron in repos inactive ~60 days (acceptable; manual dispatch still works).
- `workflow_dispatch`: explicit `version` input (final or rc) — the release-train / lane-re-bump path.

**Version check (schedule path)**

- Query `repos/vig-os/devkit/releases/latest` (public; excludes prereleases and drafts by construction — cron never proposes an rc).
- Compare against `.vig-os` `DEVKIT_VERSION`; exit no-op when current or ahead (a consumer on an rc of a newer train must not be "upgraded" backwards to the older final).
- **Opt-out knob**: `.vig-os` key `DEVKIT_AUTO_UPGRADE=true|false`, default `true`. Gates the schedule path only; `workflow_dispatch` always works (runtime gate, no re-scaffold to flip; align with #1284 manifest work if it lands first).

**Upgrade steps** (shared by both triggers)

1. Checkout base branch per workflow model (`DEVKIT_WORKFLOW`: gitflow → `dev`, trunk → `main`).
2. Create adoption issue `chore: adopt devkit <X>` (traceability; reuse the open one across rc→rc→final within a train, force-updating branch + PR).
3. Branch `chore/<issue>-devkit-<x-y-z>` (dots→dashes; the branch guard rejects dots and non-listed prefixes).
4. Runner prep: docker (present on ubuntu-latest; install.sh auto-detects) + nix (installer action) for the `flake update vigos` leg.
5. `install.sh --force --version <X> <path>` — pulls the image, regenerates the scaffold, writes the pin, advances `flake.lock`.
6. Stage/commit **inside the project shell** (`nix develop -c git commit …`) so hooks run: dist rebuild (commit-action), trailer strip, `validate-commit-msg`. Message `chore: adopt devkit <X>` + `Refs: #<issue>` (chore is Refs-exempt but include it).
7. Exclusions knob: paths listed in a new `.vig-os` key (e.g. `DEVKIT_UPGRADE_EXCLUDE`) are reset before commit — needed for vault's generate-docs PDF churn.
8. Open PR via `gh` with `Closes #<issue>` in the body.

**Token**

- PRs created with the default `GITHUB_TOKEN` do not trigger CI — a dedicated identity is required even though everything is same-repo.
- Fine-grained PAT or GitHub App with `contents:write` + `pull-requests:write` + `issues:write` on the consumer repos, stored as an org secret (verify org-secret availability for private repos on the Free plan at provisioning time; per-repo secrets are the fallback).
- Commit author = the token's bot identity; must not match `.github/agent-blocklist.toml` (the blocklist currently flags the `github-actions[bot]` email — use the dedicated identity, verify against `validate-commit-range` in consumer CI).
- Provisioning checklist: create identity, grant repos, set secret, document rotation.

**Out of scope**: auto-merge (human merges; the #1295 drift gate + full CI are the evidence), devkit's own repo (bespoke release flow), non-scaffolded consumers, push-based fan-out (see alternatives).

### Alternatives Considered

- **Hosted Renovate**: cannot execute `install.sh` (`postUpgradeTasks` is self-hosted-only); a pin-only bump produces exactly the unguarded pin/scaffold skew (#1093) that #1295 exists to catch.
- **Self-hosted Renovate + `postUpgradeTasks`**: feasible but requires a second Renovate instance, `allowedCommands`, and nix + a container runtime inside the Renovate environment — ongoing maintenance for no fidelity gain over a first-party workflow.
- **Push fan-out (`repository_dispatch` from devkit promote)**: instant latency, but needs a consumer registry, a cross-repo dispatch token, and promote-job changes; polling + manual dispatch covers the same need with strictly less machinery.
- **Committing outside the shell + separate dist-rebuild step**: duplicates hook logic (SSoT violation).

### Impact

All 5 consumers; each adoption PR becomes review-and-merge. Steady-state upgrades arrive within a week of a release with zero devkit-side action; release trains use manual dispatch (one `gh workflow run` per consumer). Backward compatible; opt-out available.

### Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on July 30, 2026 at 08:54 AM_

Implemented in PR #1298, merged to dev @4772c62f. Ships with 1.5.0.

