---
type: issue
state: closed
created: 2026-08-11T12:18:11Z
updated: 2026-08-11T12:59:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1423
comments: 1
labels: feature, area:workspace, area:workflow, effort:large, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:05.368Z
---

# [Issue 1423]: [feat: synthesize bot changelog entries at release time (drop per-PR pipeline)](https://github.com/vig-os/devkit/issues/1423)

### Description

Replace the per-PR Renovate/adoption changelog automation (`renovate-changelog-build.yml` + `renovate-changelog-commit.yml`) with release-time synthesis: a new `vig-utils` command generates all bot-PR changelog entries at the two dispatch points that already own changelog mutation — release cut (`prepare-release`) and finalize (`release.yml` / `release-core.yml`) — as a regenerated `#### Dependencies` block with net-delta coalescing per dependency.

### Problem Statement

The per-PR pipeline (#506 Option A) commits a changelog entry into every Renovate/adoption PR branch. This causes:

1. **Serial merge conflicts** — N open Renovate PRs all edit the same `## Unreleased` lines; merging one conflicts the rest. Worse, the bot's commit author (`commit-action-bot[bot]`) is not in `gitIgnoredAuthors`, so Renovate treats the branch as human-modified and never self-rebases (`rebaseWhen: conflicted` is dead wiring). Every Monday batch requires manual conflict chaining.
2. **Double CI per Renovate PR** — the bot commit's `synchronize` event re-runs the full pipeline.
3. **Lockfile-maintenance PRs get no entry** — `lock file maintenance` titles match no parser pattern and fall through the "no updates parsed" escape hatch. Verified in devkit (#1315, #1369) and consumers (commit-action#139, sync-issues-action#178). These are precisely the transitive-vulnerability PRs `lockFileMaintenance` was enabled for (#1041) — a gap, not a design decision (no pinning test, no documented carve-out).
4. **Latent release-branch bug** — `renovate-changelog-build.yml` has no base-branch filter; a bot PR based on `release/X.Y.Z` inserts its entry into the empty post-freeze `## Unreleased`, silently missing the release it ships in.
5. **Noise entries for versions that never shipped** — e.g. 1.4.2 lists `github/codeql-action` twice (#1266 `7188fc3 → e4fba86`, #1312 `e4fba86 → f205ea1`); the intermediate digest never existed in a published release.

### Proposed Solution

**New command `synthesize-bot-changelog`** (in `vig-utils`, reusing the `renovate_changelog_pr.py` parsers):

- Enumerate commits in `<last-stable-tag>..HEAD` (prerelease tags excluded; prefix-aware for consumers; full history when no tag), extract PR numbers from subjects, fetch PR metadata via `gh api`, keep PRs authored by `renovate[bot]` / `vigos-devkit-upgrade[bot]`.
- Flatten `(package, old, new, PR)` tuples across all bot PRs (including grouped-PR table rows), group by package, order by `merged_at`, and emit **one net-delta line per package**: earliest old → latest new, all contributing PRs cited. Zero net delta → no line.
- **Lockfile maintenance**: recognized by title, coalesced per ecosystem: `- Lock file maintenance (pip) ([#a](…), [#b](…))`.
- **Adoption PRs**: coalesced to the latest (shipped) devkit version, all PRs cited, release-notes link preserved.
- Entries render under a `#### Dependencies` sub-heading inside `### Changed` (matching the `#### Modules` convention). The block is **regenerated wholesale** on every run (deterministic from the enumeration window ⇒ idempotent by construction; mid-train extension of a coalesced entry works). Hand-written entries are never touched.
- Target section: `## [X.Y.Z] - TBD` when `--version` is given (finalize on the release branch), else `## Unreleased` (cut on dev/main).

**Wiring (devkit root + scaffold mirror):**

- `prepare-release.yml`: validate job runs the synthesizer before `prepare-changelog validate` (a train whose only content is bot PRs must pass the non-empty gate); prepare job runs it before `prepare-changelog prepare` — entries ride the existing freeze commit, mirror handled by the existing extension step. Jobs gain `pull-requests: read` and full-depth/tagged checkout.
- `release.yml` (devkit) / `release-core.yml` (scaffold): finalize runs the synthesizer with `--version $VERSION` before `prepare-changelog finalize` — entries ride the existing finalize commit. **This is the retrigger guarantee**: any bot PR merged into the release branch mid-train is reachable from HEAD at finalize; a bot PR merged after finalize is outside the tagged SHA and forces a re-finalize by construction. Candidates stay changelog-neutral.
- **Delete** `renovate-changelog-build.yml` + `renovate-changelog-commit.yml` (root and `assets/workspace/`), their `scripts/manifest.toml` entry, and retire both scaffold paths via `retired_paths()` (#1348).
- Optional visibility: `just changelog-preview` runs the synthesizer dry against the working tree (no commits).

**What this restores/repairs:** Renovate branches stay pristine ⇒ stock `rebaseWhen: conflicted` self-rebase works again (no `gitIgnoredAuthors` patch needed); half the CI spend per Renovate PR; latent bugs 3–5 above die.

### Alternatives Considered

- **`gitIgnoredAuthors` one-liner** (keep per-PR pipeline, let Renovate discard+regenerate the bot commit): fixes conflict tedium but keeps double CI, lockfile gap, release-branch bug, and O(N²/2) rebase CI churn.
- **Push-triggered synthesis on `release/**`**: resurrects the privileged self-committing machinery being deleted (#863 loop class), breaks the "pushes are changelog-neutral; finalize is the single stamping pass" invariant, adds an App-writable surface — for entries nobody needs before finalize (approval deliberately lands after finalize).
- **Nightly materialization on dev**: scheduled commits to `CHANGELOG.md` conflict with every open human PR editing `## Unreleased` (reintroduces the disease), needs a scheduled privileged writer on a protected branch, serves no consumer. Mid-cycle visibility is served read-only by `just changelog-preview`.
- **Ground-truth lockfile/pin diffing** (tag..HEAD tree diff instead of PR metadata): immune to reverts, but needs a parser per ecosystem (uv.lock, package-lock.json, flake.lock, action pins). Out of scope; PR-metadata coalescing is the right proxy — a reverted bump conventionally gets its own hand-written `revert:` entry.

### Additional Context

- #506 recorded this exact design as "Option C — batch at release time"; its cons (Unreleased not reflecting updates mid-cycle, prepare-release changes) are accepted/mitigated above.
- Supersedes the delivery pipeline of #1404 (adoption entries) — the entry format and its tests survive; only the transport changes. #1404 was never live-proven at a train.
- Release-train facts this design leans on: changelog mutation is exclusively dispatch-driven (cut freeze on dev + idempotent finalize on the release branch); candidates make no changelog changes; nothing runs on push to `release/**`; approval lands after finalize; the release tag becomes an ancestor of dev via `sync-main-to-dev` (window boundary is well-defined; the whole-window regeneration makes an unmerged sync PR at cut time harmless).
- Consumers get the new command via the pinned toolchain (image / dev-shell / `uv tool install` in bare mode); trunk consumers work unchanged (window = `tag..HEAD` on main).

### Impact

- All repos consuming the scaffold; semver:minor (scaffold-impacting feature).
- Consumers keep already-committed per-PR entries (historical sections untouched); in-flight bot PRs opened under the old pipeline simply stop receiving bot commits after adoption.

### Changelog Category

Changed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 12:59 PM_

Shipped to dev via PR #1425 (merge 8045470f): `synthesize-bot-changelog` replaces the per-PR renovate-changelog pipeline — synthesis at cut (`prepare-release.yml`) and finalize (`release.yml`/`release-core.yml`, final kind only), net-delta coalescing per dependency, lockfile-maintenance rollups (closing the silent gap), adoption entries coalesced to the shipped version, pair retired at 1.8.0 for consumer pruning, `just changelog-preview` for read-only visibility.

Live-proven against real PR metadata pre-merge (grouped #1368 → four old→new rows, digest #1367, lockfile #1369). First end-to-end exercise in anger lands at the next train's cut/finalize. Out of scope (recorded): reverted-bump overstatement inherent to PR-metadata coalescing.

