---
type: issue
state: open
created: 2026-10-05T18:46:25Z
updated: 2026-10-05T18:46:25Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1834
comments: 0
labels: feature, priority:medium, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:50:56.346Z
---

# [Issue 1834]: [mkRustProject: per-test exclusion seam for tests the Nix sandbox cannot run (PTY, signals, process groups)](https://github.com/vig-os/devkit/issues/1834)

### Description

`mkRustProject`'s `nextest` and `doctest` checks run inside the Nix build sandbox. Some test suites cannot run there: tests that need a PTY, process groups or signals (CLI wrappers, supervisors), plus anything that touches the network or `$HOME`. On darwin the sandbox is stricter still. Today a consumer has two choices: switch the whole check off (`nextest = false`), which also stops `nix flake check` from running every test that *would* work, or patch it through `craneArgs`. That route is undocumented, and it leaves the excluded tests with no home at all.

Split out of the open question on #1833.

### Proposed Solution

- A `nextestExtraArgs` / `sandboxExcludes` seam on `mkRustProject`: a list of nextest filter expressions (e.g. `test(pty_)`, `binary(supervisor)`) that the sandboxed `checks.nextest` skips.
- The excluded tests stay first-class outside the sandbox: the seeded Rust `justfile.project` (#1496) runs the full suite with `cargo nextest run`, so `just test` and CI still execute them.
- Document the seam in the pack's README section, including the darwin note.

### Alternatives Considered

- `crateOverrides.<name>.doCheck = false`: per-crate and all-or-nothing, so it doesn't help a workspace with one PTY test.
- `#[ignore]` + `--run-ignored` in `just test`: works, but it hijacks `#[ignore]`'s meaning and is invisible from the flake.

### Changelog Category

Added

Refs: #1833

