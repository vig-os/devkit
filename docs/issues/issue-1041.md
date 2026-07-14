---
type: issue
state: open
created: 2026-07-14T08:45:13Z
updated: 2026-07-14T15:19:27Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1041
comments: 1
labels: bug, priority:high, area:workspace, effort:small, semver:patch, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:29.893Z
---

# [Issue 1041]: [[BUG] Renovate preset does not remediate transitive npm vulns — 12 of 21 alerts unreported, including the only critical](https://github.com/vig-os/devkit/issues/1041)

## Description

The scaffolded Renovate preset (`assets/workspace/.github/renovate-default.json`)
never remediates **transitive** npm vulnerabilities. Renovate only raises security
PRs for dependencies it can see in `package.json` (`dependencies`,
`devDependencies`, `overrides`), so a vulnerable package that is only reached
through a parent is invisible: it appears in neither the Dependency Dashboard nor
any PR, while the GitHub Dependabot alert stays open indefinitely.

Renovate has a dedicated switch for exactly this — [`transitiveRemediation`][1] —
and the preset does not set it (default `false`).

[1]: https://docs.renovatebot.com/configuration-options/#transitiveremediation

## Steps to Reproduce

Observed in `vig-os/commit-action` on Renovate's first run after devkit 1.1.0
adoption (dashboard `vig-os/commit-action#42`):

1. Repo has 21 open Dependabot alerts.
2. Renovate runs, creates the Dependency Dashboard and security PRs.
3. Only the alerts whose package is **direct** in `package.json` get a PR.

## Expected Behavior

Every open Dependabot alert is represented in the Dependency Dashboard — as a
security PR, an awaiting-schedule entry, or at minimum a detected dependency.

## Actual Behavior

**9 of 21 alerts covered. 12 missing, including the only `critical`.**

| Package | Scope | Alerts | Reachable from `package.json`? | In dashboard? |
|---|---|---|---|---|
| `undici` | runtime | 9 (4 high) | ✅ direct (in `overrides`) | ✅ security PR → `6.27.0` |
| `handlebars` | development | 7 (**1 critical**, 3 high) | ❌ transitive | ❌ |
| `js-yaml` | development | 2 (medium) | ❌ transitive | ❌ |
| `@babel/core` | development | 1 (low) | ❌ transitive | ❌ |
| `flatted` | development | 1 (high) | ❌ transitive | ❌ |
| `picomatch` | development | 1 (medium) | ❌ transitive | ❌ |

The split is exactly direct-vs-transitive. `undici` is only covered because it
happens to be pinned in `overrides`, which Renovate extracts as a dependency —
i.e. coverage here is incidental, not by design.

Parent chains for the 12 missing (`npm ls`):

```
ts-jest@29.4.6 → handlebars@4.7.8            ← the critical
eslint@8.57.1  → flat-cache → flatted@3.3.3
eslint@8.57.1  → @eslint/eslintrc → js-yaml@4.1.1
jest@29.7.0    → istanbul-lib-instrument → @babel/core@7.28.5
jest@29.7.0    → jest-haste-map → anymatch → picomatch@2.3.1
```

None is declared in `package.json`, so Renovate's `Detected Dependencies` lists
only the 15 direct entries and the 12 alerts have nothing to attach to.

## Environment

- **Consumer**: `vig-os/commit-action` (devkit 1.1.0, `DEVKIT_MODE=direnv`)
- **Preset**: `assets/workspace/.github/renovate-default.json`, copied into consumers
  **verbatim** (`diff` is empty) and referenced via
  `"extends": ["github>{{GITHUB_REPOSITORY}}//.github/renovate-default"]`
- **Renovate**: hosted Mend app, GitHub platform

## Possible Solution

Set `transitiveRemediation` in the shared preset:

```diff
 {
   "$schema": "https://docs.renovatebot.com/renovate-schema.json",
   "extends": ["config:recommended"],
   "timezone": "Etc/UTC",
   "schedule": ["before 9am on monday"],
   "baseBranchPatterns": ["dev"],
   "rebaseWhen": "conflicted",
+  "transitiveRemediation": true,
```

Renovate constraints to be aware of (worth a comment in the preset):

- npm / Node.js only — a no-op for the `pep621`, `nix` and `github-actions`
  managers, so it is safe to set unconditionally in the shared preset.
- GitHub platform only — satisfied.
- Applies to **vulnerability alerts** only, not routine updates. That is precisely
  the gap here.

It remediates by bumping the top-level parent (or editing the lockfile) rather than
by adding a pin, which is the outcome we want — see below.

### Why not just pin them

Pinning transitive vulns in `overrides` is the workaround available today, and
`commit-action` shows why it is a trap: `undici` is currently pinned there to
`6.23.0` — *the vulnerable version*. A pin added to fix yesterday's advisory
silently becomes the thing blocking tomorrow's fix. `transitiveRemediation` moves
the parent instead, leaving no pin to rot.

## Blast radius

Every scaffolded repo with an npm manager. Today: `vig-os/commit-action`,
`vig-os/sync-issues-action`, and devkit itself (its own `renovate.json` sets
`enabledManagers` including `npm`).

Given the preset is what defines security posture across the org, and it currently
lets a `critical` sit unreported, this is worth more than a routine patch.

## Related

- `vig-os/commit-action#42` — the dashboard showing the gap
- `vig-os/commit-action#41` — the one security PR Renovate *did* raise (`undici`)
- vig-os/devkit#1034 — separate scaffold bug found in the same rollout pilot

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:30 AM_

## Re-scope: upstream-blocked; interim shipped in #1049

Investigation for the fix found the proposed `transitiveRemediation: true` is **no longer possible**:

- The option is in Renovate's `removedProperties` set and absent from the options schema of the validator-pinned version (43.262.3) — adding it fails our own `renovate-validate.yml` (`--strict` treats the migration warning as an error) and Renovate would discard it anyway.
- There is no drop-in replacement: `osvVulnerabilityAlerts` does not reach transitive deps, and alert-driven transitive remediation is unimplemented — see [renovatebot/renovate discussion #41825](https://github.com/renovatebot/renovate/discussions/41825).

**Interim shipped (#1049):** weekly `lockFileMaintenance` in the shared preset (same Monday cadence), which regenerates lockfiles and picks up **in-range** transitive fixes — including the `ts-jest → handlebars` chain carrying the critical alert, when parent ranges allow. Devkit's root `renovate.json` already used this mechanism; its duplicate block is removed in favor of the preset (SSoT).

**What remains open (this issue now tracks it):** alert-*driven* transitive remediation — out-of-range transitive fixes still need a manual `overrides` bump, and the Dependency Dashboard still won't represent alerts for undetected transitive packages. Revisit if/when [discussion #41825](https://github.com/renovatebot/renovate/discussions/41825) turns into a shipped feature; the preset's `lockFileMaintenance.description` carries the pointer.

---

*Edited: the upstream reference is a GitHub **Discussion**, not an issue, so the `renovatebot/renovate#41825` shorthand did not resolve — replaced with the full URL here and in the preset. Status as of 2026-07-14: open, unanswered, in the "Suggest an Idea" category (23 upvotes, last activity 2026-06-30) — i.e. a requested idea with maintainer engagement, not a planned item with a timeline. The original wording ("maintainers confirm ... planned but unimplemented") overstated it.*


