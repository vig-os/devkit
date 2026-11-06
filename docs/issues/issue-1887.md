---
type: issue
state: open
created: 2026-10-14T19:40:20Z
updated: 2026-10-14T19:40:20Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1887
comments: 0
labels: feature, area:ci, effort:medium, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:46.370Z
---

# [Issue 1887]: [[FEATURE] Rust: ship a nextest config (ci profile, timeouts, JUnit), one test entrypoint with doctests, configurable partitions](https://github.com/vig-os/devkit/issues/1887)

### Description

devkit runs Rust tests through crane's `cargoNextest` + `cargoDocTest` in `nix flake check`, but ships no nextest configuration and no matching local entrypoint. In practice, test behaviour differs between the three places tests run (local `just test`, CI, `nix flake check`).

### Problem Statement

- **No `.config/nextest.toml` is scaffolded.** There is no `ci` profile (`fail-fast = false`, `slow-timeout = { period = "60s", terminate-after = N }`), no JUnit output and no test groups for tests that must not run in parallel. The default profile is the only behaviour, so a hanging test hangs CI until the job timeout.
- **`partitions = 1` is hard-coded** in `mkRustProject`'s `cargoNextest`. Large suites can't be sharded (`--partition slice:m/n` / `hash:m/n` over an `--archive-file`).
- **Local and CI disagree.** The rust justfile's `test` recipe is `cargo test --workspace`. CI and flake checks run nextest. nextest runs each test in its own process and `cargo test` runs them as threads in one process, so global state, env-var races and timeouts behave differently. "Passes locally" then doesn't predict CI.
- **Doctests are easy to lose downstream.** nextest still doesn't run doctests ([nextest usage docs](https://nexte.st/book/usage.html)). `cargoDocTest` covers the flake check, but anything that switches its runner to `cargo nextest run` drops doctests silently. Nothing in the scaffold pairs it with `cargo test --doc`.

### Proposed Solution

1. Scaffold a managed, mergeable `.config/nextest.toml`:
   - `[profile.default]`: `slow-timeout = { period = "60s", terminate-after = 5 }`.
   - `[profile.ci]`: `inherits = "default"`, `fail-fast = false`, `failure-output = "immediate-final"`, `[profile.ci.junit] path = "junit.xml"`. Retries off by default and opt-in per test via overrides, so flakes stay visible.
   - A documented example `test-group` (`max-threads = 1`) for env-mutating or PTY tests, as the alternative to `serial_test`.
2. One test entrypoint, `just test` = `cargo nextest run --workspace` followed by `cargo test --doc --workspace`. CI's test lane calls the same recipe with `--profile ci` and uploads JUnit.
3. Expose `partitions` (and pass `cargoNextestPartitionsExtraArgs`) on `mkRustProject` instead of hard-coding 1.
4. A scaffold test asserting that doctests run under every advertised entrypoint (local, CI, flake check).

### Alternatives Considered

Keep `cargo test` as the single runner everywhere. That's simpler, but it loses nextest's per-test isolation and timeouts, which matter most when many agents and branches run suites in parallel.

### Additional Context

Complements #1811 (CI lanes run no Rust). This issue is about *how* tests run once they do.

### Impact

Downstream Rust repos; managed files change, so it's a minor bump.

### Changelog Category

Added

