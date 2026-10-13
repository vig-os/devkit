---
type: issue
state: open
created: 2026-10-12T21:34:55Z
updated: 2026-10-12T21:34:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1875
comments: 0
labels: feature, priority:high, area:ci, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:41.362Z
---

# [Issue 1875]: [[FEATURE] profiling gates: per-test memory/time caps and a perf-budget CI job](https://github.com/vig-os/devkit/issues/1875)

## Why
Downstream incident: in vig-os/stepv a single process reached 38 GB and wedged a 32-core dev host, and a human had to kill it (vig-os/stepv#83). Nothing in the scaffolded CI or the local gate bounds memory or time per test, or catches a performance regression. Every repo with a heavy native workload (Rust, C++ via FFI, ML) has the same gap. The fix belongs in the scaffold, not in each repo.

## Proposal: a "profiling gates" capability module
1. **Per-test resource caps** in the scaffolded test runner, as a nextest profile for Rust, with equivalents for other packs:
   - a memory cap per test process: Linux via cgroups/`RLIMIT_AS`, macOS via sample-and-kill;
   - a wall-time cap per test, with slow-test reporting.
   A runaway test fails, naming itself, instead of wedging the host. The same caps apply in the local gate, in the devshell's `just test`, because agents run the gate on shared hosts.
2. **A profile harness** that runs a repo-declared command per input and records peak RSS and wall time as JSON.
3. **A budget file** (`perf-budget.toml`): per-input or per-test absolute ceilings plus a regression margin against the base branch, measured on the same runner.
4. **A CI job and PR report:** it runs the harness and fails over budget or on regression, then posts a short table of the worst offenders and their deltas.
5. **Opt-in heavy tier:** large fixtures run nightly or on a label, not on every PR.

## Open questions
- The macOS memory-cap mechanism.
- How to keep noise down on shared runners (repeat runs, a median, a ratio to the base).
- The schema and naming of the budget file.
- Whether the harness lives in devkit or in a small shared crate or CLI.

## Acceptance
- A scaffolded repo gets per-test caps and the profiling job by default, with a documented opt-out.
- A deliberate memory balloon fails CI on Linux and macOS, naming the test.
- vig-os/stepv#83 adopts it as the first consumer.

Refs: vig-os/stepv#83

