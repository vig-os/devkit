---
type: issue
state: open
created: 2026-07-28T13:27:34Z
updated: 2026-07-28T13:27:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1284
comments: 0
labels: feature, priority:medium, area:workspace, effort:large, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:55.295Z
---

# [Issue 1284]: [feat(workspace): manifest-driven scaffold feature opt-outs (release, sync-issues, scanning, skills, worktree)](https://github.com/vig-os/devkit/issues/1284)

### Description

Per-consumer opt-out of managed scaffold **feature groups** via a `.vig-os` manifest key, e.g.:

```
DEVKIT_FEATURES_DISABLED="release sync-issues scanning skills worktree"
```

honored by the template copy, the stale-file prune, and `--preview` — so a disabled feature is never scaffolded, is pruned if a previous scaffold left it behind, and stays gone across `--force` upgrades.

### Problem Statement

Opting out of a managed feature today means deleting its files — and every `--force` re-scaffold re-adds them, a recurring prune tax that grows with upgrade frequency. For solo/private/data consumers, whole subsystems are inert or unwanted:

- the multi-stage **release** pipeline (~9 workflows) on repos that never cut releases;
- **sync-issues** (tunable via `DEVKIT_SYNC_TARGET`/`DEVKIT_SYNC_SCHEDULE` per #1228, but not disableable) on repos that file no issues;
- **codeql/scorecard** on private repos (cf. #1039);
- the 33 **agent skills** oriented at the issue→branch→PR SDLC;
- the **worktree** autonomous-agent recipes.

A dry-run adoption of devkit on a private single-user data repo leaves ~10 dead workflow files that resurrect on every upgrade.

### Proposed Solution

- A **feature → path-set map** as a single source of truth next to `MODE_CONFIG_EXCLUDES` in `init-workspace.sh`. Disabled features feed:
  1. the rsync copy excludes (mechanism exists: #1196),
  2. the DELETIONS prune (precedent: gitflow→trunk pruning of `sync-main-to-dev.yml`, #1208),
  3. the `--preview` classifier (must stay truthful, #1196).
- Manifest key round-trips across upgrades like `DEVKIT_TAG_PREFIX`/`DEVKIT_FLOATING_TAGS` (#1116); clearing the key re-ships the features on the next `--force`.
- **Naming:** deliberately *not* `DEVKIT_MODULES` — that key is reserved by #884 for Nix capability shells (`modules = ["native"]` toolchain composition). This is scaffold-level feature selection, orthogonal to toolchain capabilities; the issue should state that delimitation explicitly.
- **v1 scope:** features whose surface is standalone files (workflow files, `.claude/skills/`, justfile import fragments). Jobs *inside* `ci.yml` (e.g. dependency-review) are out of scope for v1 — `ci.yml` stays atomic.

#### Acceptance criteria

- [ ] Key + feature names documented in the `docs/MIGRATION.md` manifest table
- [ ] Disabled features are neither copied nor listed as ADDED in `--preview`; pre-existing copies are pruned and listed under DELETIONS
- [ ] Empty/absent key → byte-identical scaffold to today
- [ ] Re-enabling (key edit + `--force`) restores the features
- [ ] bats coverage: disable, upgrade-stability, re-enable, preview truthfulness

### Alternatives Considered

- **Status quo** — delete after every upgrade; recurring cost, error-prone, and `--preview` reports the re-adds as intended.
- **Splitting features into separate repos/templates** — heavyweight, breaks the single-scaffold upgrade story.
- **Profiles only** (e.g. a single `solo` switch) — less granular; profiles are better layered *on top* of this key as documented presets (companion docs issue to follow).

### Additional Context

#884/#885 (manifest namespace and reserved `DEVKIT_MODULES`), #1205/#1208 (workflow-model knob — the closest existing precedent for a consumer-shape scaffold switch), #1196 (preview/copy exclude SSoT), #1039 (private-repo scanning guard), #1228 (sync-issues knobs), #1282 (Refs policy knob — companion consumer-policy key). Motivated by a devkit-adoption evaluation for a private single-user repo, but equally useful for any org repo consuming a subset (e.g. a docs-only repo without the release train).

### Impact

- Benefits solo/private consumers and subset-consumers across the org; removes the recurring prune tax and makes `--preview` reflect intent.
- Backward compatible (`semver:minor`); absent key changes nothing.

