---
type: issue
state: open
created: 2026-07-16T19:43:27Z
updated: 2026-07-16T19:43:27Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1159
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:01.167Z
---

# [Issue 1159]: [release-core finalize commits the whole dist/ (force-includes gitignored tsc emit), re-tracking dist/src + *.tsbuildinfo every release](https://github.com/vig-os/devkit/issues/1159)

## Summary

`release-core.yml`'s finalization step commits the **entire `dist/` directory** for bundle projects, force-including files that the project's `.gitignore` deliberately excludes (`dist/src/**`, `dist/*.tsbuildinfo`). This silently re-tracks tsc/ncc byproducts on every final release, defeating the "ship only the bundle" invariant that the seeded `.gitignore` + `dist-check.yml` establish, and making the sanctioned `git rm --cached` cleanup impossible to persist.

## Where

`assets/workspace/.github/workflows/release-core.yml`, the finalize commit step:

```yaml
FILE_PATHS: ${{ steps.bundle.outputs.has_bundle == 'true' && 'CHANGELOG.md,dist' || 'CHANGELOG.md' }}
```

`just bundle` runs `tsc` (emitting `dist/src/**` + `dist/tsconfig.tsbuildinfo`) and `ncc` (emitting `dist/index.js` + `dist/licenses.txt`). Passing `dist` (the whole dir) to `commit-action` commits **all** of those — the gitignored tsc byproducts included.

## Why it's wrong

The downstream seed already declares the intended tracked set (see the `dist-check.yml` header and `.gitignore`):

> tracked artifacts are `dist/index.js` + `dist/licenses.txt`; everything else under `dist/` is gitignored

`dist-check.yml` even runs `git status --porcelain -- dist/` (whole dir) precisely to catch stray/uncommitted `dist/` output. But the finalize commit re-introduces exactly those stray files, so the two mechanisms contradict each other.

## Impact

- Every final release re-commits `dist/src/**` + `dist/tsconfig.tsbuildinfo` (fresh content), re-tracking them on `main` (and on `dev` via `sync-main-to-dev`) and in the release tag tree.
- Mostly latent because the emit is re-freshened each release — **but** it re-bites as a **release-PR `Dist Check` failure** whenever a dep bump changes tsc/ncc output without a rebuild on the (intentionally un-gated) `dev` branch. That is exactly what blocked `sync-issues-action` v0.4.0 (a `@vercel/ncc 0.38→0.44` bump changed emit; `dist/tsconfig.tsbuildinfo` drifted on the release PR).
- The documented recovery — a bugfix PR that `git rm --cached dist/src dist/tsconfig.tsbuildinfo` — clears the release-PR gate but **cannot persist**: the subsequent finalize commit re-adds everything.

## Evidence

- `sync-issues-action` bugfix PR that untracked the emit: vig-os/sync-issues-action#136
- The finalize commit that re-added it (13 files, +5067) immediately after: vig-os/sync-issues-action@7ba6ae6 (`chore: finalize release 0.4.0`)
- Result: `git ls-tree v0.4.0 dist/` still lists `dist/src` + `dist/tsconfig.tsbuildinfo`.
- Seen on `DEVKIT_VERSION=1.3.0`.

## Proposed fix (either level)

1. **release-core.yml** — commit only the shipped artifacts, not the whole dir. Since the tracked set varies per project, prefer respecting existing tracking rather than a hardcode: commit `CHANGELOG.md` + only the non-ignored `dist/` files (i.e. `git add`-with-`.gitignore` semantics), or expose a `DEVKIT_DIST_PATHS` knob (default `dist/index.js,dist/licenses.txt`).
2. **commit-action** — when a directory path is given in `FILE_PATHS`, honor `.gitignore` (don't force-add ignored files under it). This is the more general fix and keeps `FILE_PATHS: CHANGELOG.md,dist` correct.

## Related

Distinct from #1157 (native promote floating-tag create-vs-update 422), but both surfaced on the same `sync-issues-action` v0.4.0 / `commit-action` v0.3.1 release trains.

