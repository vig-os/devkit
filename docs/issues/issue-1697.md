---
type: issue
state: closed
created: 2026-09-25T07:50:07Z
updated: 2026-09-25T10:40:09Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1697
comments: 2
labels: chore, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:44.593Z
---

# [Issue 1697]: [[CHORE] Declare bats_require_minimum_version in every BATS file to silence the BW02 warnings](https://github.com/vig-os/devkit/issues/1697)

### Chore Type

General task

### Description

No file under `tests/bats/` declares `bats_require_minimum_version`, so
every run of the suite prints a `BW02` warning per use of a flag on `run`
(`run --separate-stderr`, `run -0`, …): bats 1.5+ gates those flags behind
the declaration and warns when it is missing. The suite is on bats 1.12.0
from the flake, so the declaration is safe everywhere the suite runs.

Cosmetic, but it is noise on every local and CI log, and with `bats -j`
(#1687) the warnings interleave with TAP output, which makes a real
`not ok` harder to spot.

### Acceptance Criteria

- [ ] Every `tests/bats/*.bats` file that uses a `run` flag declares
      `bats_require_minimum_version 1.5.0` at the top (after the shebang,
      before `setup`); files that never pass a flag may declare it too for
      uniformity — pick one rule and apply it to all 21 files
- [ ] `bats -j "$(nproc)" tests/bats/ 2>&1 | grep -c BW02` is `0`
- [ ] 602/602 green, no test changed beyond the declaration

### Implementation Notes

- One line per file; no behaviour change. bats docs:
  <https://bats-core.readthedocs.io/en/stable/warnings/BW02.html>
- `test_helper.bash` is `load`ed inside `setup`, which is too late for the
  declaration (it must be at file top level), so it cannot be centralised
  there.

### Related Issues

- Noted in #1687's Additional Context; PR #1690

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 10:28 AM_

Three corrections, from implementing this (PR branch `bugfix/1694-worktree-bats-isolation`):

1. **"No file under `tests/bats/` declares `bats_require_minimum_version`" is wrong.**
   `githooks.bats:10` already declares it. 20 of the 21 files needed the line, not 21.
2. **The suite emits exactly one `BW02`, not "one per use of a flag on `run`".** There is a
   single flagged `run` in the whole suite: `init-workspace.bats:1801`
   (`run --separate-stderr`). Measured before the fix: `grep -c BW02` = 1.
3. **It does not interleave with TAP output.** bats collects warnings and prints them in a
   trailing "The following warnings were encountered during tests:" block after the plan, so
   it never sits between `ok`/`not ok` lines — including under `bats -j`.

None of that changes the verdict: the acceptance criteria are met as written and the value is
drift-proofing, since the next `run -0` or `run --separate-stderr` added to any of the 21
files would reintroduce the warning. That is now pinned by a parametrized pytest
(`tests/test_bats_shape.py`) rather than left to review, so the rule survives new files too.
`grep -c BW02` over `bats -j 8 tests/bats/` is 0 and the suite is 602/602.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 10:40 AM_

Shipped to `dev` in #1709: bats_require_minimum_version 1.5.0 in all 21 files, pinned by tests/test_bats_shape.py; BW02 count 0 in CI.

