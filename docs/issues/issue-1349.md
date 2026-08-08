---
type: issue
state: closed
created: 2026-08-07T08:11:31Z
updated: 2026-08-07T09:32:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1349
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:05.650Z
---

# [Issue 1349]: [fix(install): preserved-file template diffs render as symlink add/delete, not content diffs](https://github.com/vig-os/devkit/issues/1349)

## Problem

On `--force` upgrades the installer prints a diff between each preserved consumer file and the incoming template so the consumer can fold in template evolution (MIGRATION.md 0.3.x checklist item 2). But devkit's assets are nix-store **symlinks**, so every one of these diffs renders as "symlink deleted / workspace file added" instead of an actual content comparison — the diff is useless for its stated purpose.

Observed on the vig-os/scitadel 0.3.3 → 1.6.0 migration (issue vig-os/scitadel#207): all four preserved-file diffs (`.pre-commit-config.yaml` among them) had to be redone by hand against `devkit/assets/workspace/`.

## Expected

Dereference the template side (e.g. `diff -L template <(cat "$(readlink -f "$tpl")") "$consumer_file"` or `--no-dereference`-aware handling) so the printed diff compares contents.

## Workaround

Manually diff the preserved file against the resolved file under `assets/workspace/` in the devkit checkout.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 09:32 AM_

Fixed on dev by PR #1354: the preserved-file template diff now dereferences symlinked templates (content materialized under the file's own name in a temp dir), so --force upgrades print a real content diff instead of a symlink typechange. Ships with the next devkit release.

