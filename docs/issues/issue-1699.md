---
type: issue
state: closed
created: 2026-09-25T08:46:39Z
updated: 2026-09-25T16:23:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1699
comments: 2
labels: bug, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:43.893Z
---

# [Issue 1699]: [[BUG] teardown_file failures do not fail the bats run (exit 0)](https://github.com/vig-os/devkit/issues/1699)

### Description

On bats 1.12.0 (the flake's `batsWithLibs`), a failing `teardown_file` is reported as `not ok N teardown_file failed` in the TAP stream **but the `bats` process exits 0**. Verified during the #1694 spike with a minimal file:

```bash
teardown_file() { return 1; }
@test "noop" { true; }
```

```
1..1
ok 1 noop
not ok 2 teardown_file failed
# (from function `teardown_file' in test file t.bats, line 1)
#   `return 1' failed
$ echo $?
0
```

Consequence for this repo: any invariant checked in a `teardown_file` (the natural place for a "the suite left the world unchanged" pin, which is exactly what #1694 first considered) can go red in the log while CI stays green. `test-project/action.yml` runs `bats -j "$(nproc)" tests/bats/` and gates on the exit code only.

### Steps to Reproduce

1. Save the two-line file above as `t.bats`
2. `nix develop --command bats t.bats; echo $?`

### Expected Behavior

A `teardown_file` failure fails the run (non-zero exit), the same way a `setup_file` failure does.

### Actual Behavior

`not ok` line printed, exit code 0.

### Environment

- **OS**: any
- **Container Runtime**: n/a
- **Image Version/Tag**: dev-shell bats 1.12.0 from the flake
- **Architecture**: any

### Additional Context

Found while spiking #1694 (a `teardown_file` snapshot of the live `<repo>-worktrees` directory was rejected as the red-first pin for this reason; the pin landed as a per-test assertion instead). No test in `tests/bats/` currently relies on `teardown_file` failing, so this is a latent hole, not a live one.

### Possible Solution

- Check whether bats upstream tracks this (bats-core issue tracker, `teardown_file` exit code) and whether a newer bats in nixpkgs fixes it; if so, the pin advance is the fix.
- Otherwise, guard in `test-project/action.yml` and `just test-bats`: capture TAP output and fail on `^not ok .* teardown_file failed` regardless of the exit code.
- Either way, a shape test that greps `tests/bats/*.bats` and refuses assertions inside `teardown_file` until the hole is closed.

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: the reported exit code does not reproduce

The two-line repro from the description, run against the flake's `bats` (1.12.0), exits **1** in every mode tried — plain, `-j 4`, directory target, `--formatter tap` and `pretty`, and the exact `nix develop --command bats t.bats; echo $?` form:

```
1..1
ok 1 noop
not ok 2 teardown_file failed
# (from function `teardown_file' in test file t.bats, line 1)
#   `teardown_file() { return 1; }' failed
# bats warning: Executed 2 instead of expected 1 tests
EXIT=1
```

Same result on bats 1.14.0 (the `nixpkgs-unstable` input). The exit code is set explicitly in `bats-exec-file` (`bats_file_exit_trap`, `bats_exec_file_status=1` on the `teardown_file` branch) and propagated by `bats-exec-suite` on both the serial and the parallel path. Every upstream `teardown_file` exit-code issue (bats-core #588, #615, #623, #695, #916) is closed. Note the pasted output in the description lacks the `bats warning: Executed 2 instead of expected 1 tests` line bats always prints here, so `$?` in the spike was most likely read after a pipeline (`| tee` or similar), not from bats.

**Three genuine silent-pass paths do exist** (all reproduced, exit 0, and none prints `not ok`):

1. `setup_file` calls `skip` → a failing `teardown_file` is swallowed entirely (deliberate upstream, bats-core#695).
2. `--filter` / `--filter-status` selecting zero tests in a file → the file body never runs.
3. A failing command inside a pipeline in `teardown_file` (`false | cat`) → plain bash pipeline status, no `pipefail`.

A TAP-grep guard (Possible Solution 2) would catch none of these and would add output parsing to both invocation sites for a code path that already works; a pin advance (Possible Solution 1) has nothing to fix.

**Disposition:** land only the shape pin (Possible Solution 3): `tests/test_bats_shape.py` refuses `teardown_file` in `tests/bats/*.bats` (empty allowlist), with the three swallow paths documented in its docstring. No `teardown_file` exists in the suite today, so the gate starts green.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 04:23 PM_

Closing as not reproducible as filed: a failing `teardown_file` exits 1 on bats 1.12.0 and 1.14.0 in every mode (evidence in the triage comment above). The three real swallow paths are now guarded by a shape pin refusing `teardown_file` in `tests/bats` (#1720, merged to `dev` at ac90505a).

