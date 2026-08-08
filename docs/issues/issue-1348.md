---
type: issue
state: closed
created: 2026-08-07T08:03:59Z
updated: 2026-08-07T09:06:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1348
comments: 1
labels: bug, priority:medium, area:workspace, effort:medium, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:06.182Z
---

# [Issue 1348]: [fix(install): upgrade does not prune scaffold files retired since the consumer's pinned version](https://github.com/vig-os/devkit/issues/1348)

## Problem

`install.sh --force` prunes files the **current** scaffold manages, but files that were scaffold-shipped in an old version and have since been *retired* are left behind. Observed upgrading exo-pet/playground-carlos from 0.3.4 to 1.6.0 (exo-pet/playground-carlos#9): the upgrade preserved

- `.cursor/` (retired in 0.4.0 in favour of `.claude/`)
- `.github/actions/resolve-image/` (superseded by `resolve-toolchain`)
- `.github/workflows/renovate-changelog.yml` (superseded by the `renovate-changelog-build`/`-commit` pair — left in place it is a live workflow pointing at the deleted `resolve-image` action)
- `.hadolint.yaml` (no Dockerfile remains in direnv-mode consumers)

The `renovate-changelog.yml` case is the sharp one: the stale workflow coexists with its replacements and references a pruned action, so it breaks at the next trigger rather than at upgrade time.

## Expected

The upgrade path knows the consumer's previous pin (`DEVKIT_VERSION`/legacy `DEVCONTAINER_VERSION`); a cumulative retired-paths manifest (version → paths retired) would let `--force` prune exactly what an old scaffold shipped and the new one no longer manages — same spirit as the managed-set denylist from #1145, extended across versions.

## Workaround

Manual deletion during migration (done in exo-pet/playground-carlos#9; scitadel and h5v migrations are checking for the same leftovers).
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 09:06 AM_

Fixed by #1352, merged to `dev` @ `0c4e6b44`.

**What changed** (`assets/init-workspace.sh`):

- `PREVIOUS_PIN` — the pin `.vig-os` carried *before* the run rewrites it, read
  alongside the other manifest values well ahead of the #852 rewrite. Legacy
  `DEVCONTAINER_VERSION` included: repos still on that key are the oldest ones,
  i.e. exactly the population carrying the leftovers.
- `retired_paths()` — the cumulative manifest, one `<version> <path>` line per
  path, `<version>` being the first release that stopped shipping it. Each
  version was verified against this repo's git history:

  | Path | Retired in | Superseded by |
  |------|-----------|---------------|
  | `.github/workflows/renovate-changelog.yml` | 0.3.5 | the `-build`/`-commit` pair |
  | `.cursor/` | 0.4.0 | `.claude/` |
  | `.hadolint.yaml` | 0.4.0 | — (Debian build path decommissioned) |
  | `.github/actions/resolve-image/` | 1.1.0 | `resolve-toolchain` |

- `version_lt()` — prerelease-aware in the direction that matters (`X.Y.Z-rcN`
  sorts below `X.Y.Z`, so an rc of the retiring release still prunes).
- `retired_prune_paths()` — the single resolver consulted by **both** the
  `--preview` `DELETIONS` report and the post-copy prune, so the report can
  never disagree with what the run does. Four gates: a present, semver-shaped
  pin; the pin predates the retirement; the current template does not ship the
  path; the path is not in `PRESERVE_FILES`.

`.devcontainer/justfile.base` (also retired in 0.4.0) deliberately keeps its
dedicated block — its prune is mode-guarded (#738 never touches a direnv/bare
consumer's own `.devcontainer/`), which a version-only manifest cannot express.

**Known limitation — deliberate, not an oversight.** The prune is gated on the
previous pin, because `.cursor/` and `.hadolint.yaml` are generic names: a repo
pinned at or past the retiring version was never shipped them by devkit, so an
identically named path there is the consumer's own and deleting it would be data
loss. The flip side is that a repo which already upgraded past a retirement
*before* this fix keeps its leftovers — a one-time manual cleanup, now documented
in `docs/MIGRATION.md` step 8. If an escape hatch that ignores the pin gate
(`--prune-retired`) turns out to be wanted, that deserves its own issue rather
than widening this one.

**Verification:** new `tests/test_scaffold_retired_paths.py` — 6 tests over the
real `init-workspace.sh` covering manifest contents, prune from an old pin,
legacy `DEVCONTAINER_VERSION` pin, **no** prune past the retirement, **no** prune
without a pin, and `--preview` reporting without mutating. Full CI green — 12
pass, 1 skipping, including the in-container Image and Integration suites.

Milestoned 1.6.1.

