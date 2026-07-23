---
type: issue
state: open
created: 2026-07-22T16:32:39Z
updated: 2026-07-22T17:09:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1254
comments: 0
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-23T05:31:49.784Z
---

# [Issue 1254]: [[FEATURE] setup-labels: support a repo-local, non-managed taxonomy extension file](https://github.com/vig-os/devkit/issues/1254)

## Description

Add support for a **repo-local taxonomy extension file** (e.g.
`.github/label-taxonomy.local.toml`) that `setup-labels` merges with the
canonical, devkit-managed `.github/label-taxonomy.toml`. The extension file is
**not** devkit-managed — it is never regenerated or overwritten on devkit
upgrade — so a consuming repo can declare its own repo-specific labels without
losing them and without polluting the canonical taxonomy.

This mirrors devkit's existing justfile layering convention (base *managed* →
project *shared* → local *personal*): the canonical taxonomy is the managed
base, and the extension file is the repo-owned layer that survives upgrades.

## Problem Statement

Every devkit-consuming repo receives a devkit-managed
`.github/label-taxonomy.toml` whose header states *"regenerated on upgrade; local
edits are lost"*. `uv run setup-labels` reconciles a repo's labels from that
file, and `--prune` deletes any live label that is not in the taxonomy.

Today repo-specific labels have **no safe home**:

- They cannot be added to `label-taxonomy.toml` — the file is regenerated on
  devkit upgrade, so the additions are silently lost.
- Any `setup-labels --prune` run deletes them as "non-taxonomy" labels.

Concrete use case — `vig-os/org-config` needs four repo-specific labels:

| Label | Origin |
|-------|--------|
| `drift` | Auto-created (gray, undescribed) by the GitHub API when the drift-detection layer opens issues — `POST /repos/../issues` auto-creates missing labels. |
| `critical` | Same drift-detection path. |
| `inventory` | Same drift-detection path. |
| `change-request` | Created manually via `gh label create`; used by the new change-request issue form (see `vig-os/org-config#70`, PR `vig-os/org-config#71`). |

With the current design, `setup-labels --prune` deletes all four. The three
drift labels respawn gray/undescribed on the next drift issue; `change-request`
silently disappears until the form recreates it (again gray/undescribed). There
is no way to give these labels stable colors/descriptions or protect them from
prune.

The decision (by the org-config maintainer) is explicitly **not** to add these
org-config-specific labels to the canonical devkit taxonomy — they are
repo-local by nature. Hence the need for a repo-local extension mechanism.

## Proposed Solution

Introduce an optional, **non-managed** extension file discovered alongside the
canonical taxonomy — suggested name `.github/label-taxonomy.local.toml`
(maintainers' choice; pick a name consistent with the `justfile.local` /
`justfile.project` convention). Behaviour:

1. **Not devkit-managed.** The workspace regeneration/upgrade step never
   creates, overwrites, or prunes this file. It is owned by the consuming repo
   and committed there.
2. **Merged by `setup-labels`.** It uses the same `[[labels]]` schema
   (`name` / `description` / `color`). At reconciliation time
   `setup-labels` loads the canonical taxonomy and, if present, the extension
   file, and treats the union as the effective taxonomy (i.e. its entries are
   appended to the parsed `NAMES` / `DESCRIPTIONS` / `COLORS` arrays before the
   create/update/prune loop runs).
3. **Respected by `--prune`.** Labels declared in the extension are part of the
   effective taxonomy, so prune never deletes them. Only labels absent from
   *both* files are pruned.
4. **Collision policy.** On a `name` collision between the canonical taxonomy
   and the extension, define precedence explicitly — suggest **local wins**
   (extension overrides canonical color/description), or alternatively **error
   out** to prevent a repo from silently shadowing a canonical label. Please
   pick and document one.
5. **Discoverability.** Document the extension in the canonical taxonomy's
   header comment (the block that currently lists `setup-labels` / triage /
   issue_create consumers) so downstream maintainers discover it, plus a note
   in the relevant docs.

Implementation note: `setup-labels.sh` currently hardcodes a single
`TAXONOMY_FILE="${REPO_ROOT}/.github/label-taxonomy.toml"` and parses it into
`NAMES`/`DESCRIPTIONS`/`COLORS`. The extension can be handled by parsing a
second file (if it exists) into the same arrays before the reconciliation and
prune loops — no change to the reconciliation logic itself.

## Alternatives Considered

- **Add the labels to the canonical taxonomy** — rejected: they are
  repo-specific, and the maintainer decided not to pollute the shared taxonomy;
  also fragile across repos that don't want them.
- **Never run `--prune` in org-config** — leaves org-default label drift
  unmanaged and doesn't give the four labels stable colors/descriptions; the
  auto-created ones stay gray/undescribed.
- **Recreate labels out-of-band** (e.g. a repo workflow calling
  `gh label create`) — duplicates taxonomy logic, races with `--prune`, and
  violates single-source-of-truth.

## Additional Context

- Motivating repo/use case: `vig-os/org-config#70` (change-request issue form,
  PR `vig-os/org-config#71`) and the drift-detection layer that auto-creates
  `drift` / `critical` / `inventory`.
- Analogous existing convention: devkit's layered justfiles
  (`justfile.base` managed → `justfile.project` shared → `justfile.local`
  personal/gitignored).
- Relevant code: `packages/vig-utils/src/vig_utils/shell/setup-labels.sh`
  (single hardcoded `TAXONOMY_FILE`, `--prune` deletes any live label not in the
  parsed name set) and the header of
  `assets/workspace/.github/label-taxonomy.toml` /
  `.github/label-taxonomy.toml`.

## Impact

- **Who benefits:** any devkit-consuming repo with repo-specific labels;
  immediately `vig-os/org-config`.
- **Compatibility:** backward compatible. The extension file is optional; when
  absent, `setup-labels` behaves exactly as today. No change to the canonical
  taxonomy schema. → `semver:minor`.

## Acceptance Criteria

- [ ] `setup-labels` discovers an optional, non-managed repo-local extension
      file (e.g. `.github/label-taxonomy.local.toml`) using the same
      `[[labels]]` schema.
- [ ] When present, its labels are created/updated alongside the canonical
      taxonomy in the normal reconciliation pass.
- [ ] `setup-labels --prune` never deletes labels declared in the extension
      (only labels absent from both files are pruned).
- [ ] `--dry-run` previews extension labels correctly.
- [ ] Name-collision precedence between canonical and extension is defined and
      documented (local-wins or error).
- [ ] The extension file is never created, overwritten, or pruned by the devkit
      upgrade/regeneration step.
- [ ] The canonical taxonomy header comment (and relevant docs) mention the
      extension file so consumers discover it.
- [ ] Verified end-to-end against the `vig-os/org-config` case: `drift`,
      `critical`, `inventory`, `change-request` declared in the extension
      survive a `--prune` run with their configured colors/descriptions.

## Changelog Category

Added

