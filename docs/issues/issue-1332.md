---
type: issue
state: closed
created: 2026-08-04T07:30:15Z
updated: 2026-08-04T10:03:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1332
comments: 2
labels: feature, priority:medium, area:ci, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:54.804Z
---

# [Issue 1332]: [feat(workspace): exclude devkit-managed workflows and actions from consumer renovate](https://github.com/vig-os/devkit/issues/1332)

### Description

Consumer repos scaffolded by devkit run Renovate with the `github-actions` manager enabled, and it scans the devkit-**managed** workflows (`.github/workflows/`) and managed composite actions (`.github/actions/setup-devkit-toolchain`, `.github/actions/resolve-toolchain`), which carry SHA-pinned third-party actions. Renovate in each consumer opens PRs bumping pins inside files that the next `devkit-upgrade` regenerates wholesale.

### Problem Statement

- Duplicate PR noise: every consumer gets weekly renovate PRs for pins that devkit's own renovate already advances at the source (`assets/workspace/.github/workflows/`).
- Clobber churn: a merged downstream bump is overwritten by the next upgrade; if the consumer's renovate ran ahead of the devkit train, the upgrade PR actively **downgrades** the pin until devkit catches up.
- Doctrine violation: managed files are devkit-owned (SSoT); their dependency maintenance belongs upstream, like every other aspect of those files.

### Proposed Solution

Add a `packageRules` entry to the **shipped preset** `assets/workspace/.github/renovate-default.json` (a managed file — rolls out to every consumer on the next upgrade):

- `matchFileNames`: the enumerated managed workflow files (all shipped workflows **minus** the two consumer-owned seams `release-extension.yml` / `prepare-release-extension.yml`, which are in `PRESERVE_FILES`) plus the two managed composite action dirs.
- `enabled: false`, with a description stating pins advance via devkit releases.

Because devkit itself extends this same preset and its **root** workflows share those basenames/paths, append a re-enable `packageRules` entry (`enabled: true`) in devkit's root `renovate.json` — the extending config's rules merge after preset rules and win. The shipped copies under `assets/workspace/` are unaffected by the preset rule (rooted `matchFileNames` globs don't match nested paths) and keep updating.

Guard the enumeration with a drift-gated pytest: the preset's disabled list must equal the contents of `assets/workspace/.github/workflows/` minus the `PRESERVE_FILES` seams, plus the shipped composites — so adding/renaming a managed workflow cannot silently reopen the gap.

Document in `docs/WORKFLOW_SECURITY.md`: dependency responsibility for managed files sits upstream; consumers can opt back in via their preserved `renovate.json` (later `packageRules` win).

### Alternatives Considered

- **Status quo** — duplicate PRs ×N consumers, clobber/downgrade churn, wasted CI. Rejected.
- **Drop `github-actions` from consumers' `enabledManagers`** — too blunt: consumers own the two extension seams and may author their own workflows; those deserve coverage. Rejected.
- **`ignorePaths` in the preset** — merges un-overridably (no rule ordering), applies across all managers, and would break devkit's own root workflows with no escape hatch. Rejected in favor of an overridable `enabled:false` packageRule.
- **Exclusion in the scaffolded `renovate.json`** — that file is in `PRESERVE_FILES` (consumer-owned, never upgraded), so the change would only reach new scaffolds. Rejected.

### Additional Context

Accepted trade-off: disabling updates for managed files also suppresses Renovate vulnerability PRs for those pins downstream. Consistent with doctrine — devkit is the patch channel for managed files, and an emergency hand-bump downstream still works (the next upgrade re-converges).

While in the preset, sanity-check `baseBranchPatterns: ["dev"]` against trunk-model consumers (vault, exo-fleet, org-config) and record the finding here; fix separately if it is a real bug.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 07:43 AM_

Sanity check from the plan (baseBranchPatterns vs trunk-model consumers) is done — **confirmed a real, pre-existing bug**: the shipped preset hardcodes `baseBranchPatterns: ["dev"]` and the trunk transform never rewrites it, so Renovate is effectively inert on trunk consumers (verified live on exo-pet/vault and vig-os/org-config — both carry `["dev"]` with no `dev` branch). Filed separately as #1336; kept out of PR #1335 for minimal diff.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 4, 2026 at 08:05 AM_

Implemented in PR #1335, merged to dev @6dbec060 (ships with the next release; consumers pick the preset change up via devkit-upgrade). Preset disables Renovate for the 13 managed workflows + 2 managed composite actions; devkit root re-enables its own paths; enumeration drift-gated by tests/test_renovate_preset_managed_exclusion.py; docs in WORKFLOW_SECURITY.md. Rollout reminder: close any open downstream renovate PRs touching managed workflows — they will not be recreated. The baseBranchPatterns sanity check confirmed a separate pre-existing bug, tracked in #1336.

