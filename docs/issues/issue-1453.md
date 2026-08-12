---
type: issue
state: closed
created: 2026-08-12T09:44:34Z
updated: 2026-08-12T10:06:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1453
comments: 1
labels: docs, priority:high, area:workflow, effort:small, semver:patch
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:39.359Z
---

# [Issue 1453]: [[DOCS] 1.8.0 changelog: the #1434 entry lost its title bullet and reads as part of #1444](https://github.com/vig-os/devkit/issues/1453)

### Description

In the `## [1.8.0] - TBD` -> `### Fixed` section, the #1434 entry has **lost its bold title bullet**. Its three sub-bullets now hang off the #1444 entry.

On `release/1.8.0` (`CHANGELOG.md:200-226`), the #1444 entry reads:

```
- **Smoke dispatch template deploy branch is now dot-free** ([#1444](...))
  - The template still generated `chore/deploy-<tag>` with dots, ...   <- legitimately #1444
  - A direnv consumer on flake-generated hooks had **no local commit-  <- #1434
    message or agent-identity enforcement at all**: ...
  - `mkProjectShell` gains `commitTypes` and `refsPolicy` ...          <- #1434
  - Unset knobs keep the generated config byte-identical ...           <- #1434
```

### Impact

**The 1.8.0 release notes are wrong as they stand.** #1434 — a user-visible fix to local commit-message and agent-identity enforcement for every direnv consumer on generated hooks — has no entry of its own, and its content reads as part of an unrelated smoke-dispatch branch-naming fix. A consumer reading the notes to decide whether to adopt would not learn that local enforcement changed, which matters because adoption is itself a behavior change (a repo with non-conformant history starts seeing local rejections after `nix flake update vigos`).

### Steps to Reproduce

```
git show origin/release/1.8.0:CHANGELOG.md | sed -n '200,226p'
```

### Expected Behavior

The three #1434 sub-bullets sit under their own bold title bullet linking #1434, e.g.

```
- **Flake-generated hooks now carry the commit-message and agent-identity guards** ([#1434](https://github.com/vig-os/devkit/issues/1434))
```

placed in the `### Fixed` section per Keep a Changelog ordering, leaving #1444 with only its own sub-bullet.

### Additional Context

Most likely collateral from the changelog freeze at `046ca547`, which moved `## Unreleased` content into `## [1.8.0]`. Spotted while reviewing #1447; deliberately not repaired there to avoid an untraceable drive-by.

This must land on `release/1.8.0` **before the notes are cut** — after that the 1.8.0 section is released and immutable per the changelog rules ("never modify entries below `## Unreleased`").

Scope: repairing this one entry only. Do not touch other entries or released sections.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 10:06 AM_

Fixed by #1457, merged to `release/1.8.0` as 7e64013b — in time for the 1.8.0 notes.

A single added line; no re-indentation was needed, since the orphaned sub-bullets were already at the correct depth. `### Fixed` now reads #1447, #1443, #1444, #1434, #1414, #1403, #1396, and #1444 keeps only its own sub-bullet.

**The title was recovered, not invented.** `git show 20e5660c:CHANGELOG.md` (the PR #1439 merge) carries the exact line, #1439's body proposes it verbatim, and the restored region diffs byte-identical against the original — so the notes ship the wording #1434 actually landed with, in its original slot ahead of #1414.

**Correction to this issue's root-cause guess.** It was *not* the changelog freeze: `046ca547` only moved headings (14 insertions / 4 deletions). The culprit is `c427dee8` (#1443), whose diff shows `-- **Flake-generated hooks…**` — it *replaced* the #1434 title line instead of inserting above it. `d0f276cd` (#1444) then inserted below that and inherited the orphans.

**No test was added, deliberately.** The three sub-bullets had a perfectly valid parent (#1444), so a "every sub-bullet has a titled parent" assertion passes identically before and after and cannot express this bug. The only detecting heuristic — "a sub-bullet cites an issue other than its parent's" — is violated constantly by design here (#1447's sub-bullet cites #1434; #1443's cites #1344/#1348/#1423), so it would be almost entirely false positives. This is a semantic authorship error, not a structural one, which is also why `pymarkdown` passes it.

Every top-level bullet in the 1.8.0 section was audited post-fix; all 19 conform. One suspected second instance was chased and cleared — the #1403 entry's sub-bullets about smoke deploys preserving `CHANGELOG.md` look misparented, but `git show 64b524ac` proves all three were authored together as facets of the same fix.

Residual cosmetics, pre-existing and out of scope: stray blank lines between three `### Changed` entries (#1411, #1409, #1405) where every other section is contiguous, and trailing periods on four sub-bullets (#1403's three, #1396's one).

**Note for the train:** this defect class — a hand-inserted entry silently consuming the line beneath it — survived a PR review and the freeze and surfaced only by eye during #1447 review. The `[1.8.0]` section becomes immutable at cut, so one last read of the rendered notes before finalize is cheap insurance.

