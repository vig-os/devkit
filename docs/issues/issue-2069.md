---
type: issue
state: open
created: 2026-11-11T01:12:18Z
updated: 2026-11-11T01:12:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2069
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-11T09:09:55.779Z
---

# [Issue 2069]: [Per-repo build resource defaults for shared dev hosts (jobs, test threads, target root, disk preflight)](https://github.com/vig-os/devkit/issues/2069)

## Motivation
Several projects' build agents share one multi-core dev host. Without per-repo limits, each repo's devshell compiles and tests with every core and writes its build output wherever the tool defaults. Load spikes stall the other agents. Build directories fill the disk until builds fail with ENOSPC. Host-wide admission (slots, quotas, a janitor) belongs in the host config. The per-repo defaults belong in the opinionated dev kit, so every repo gets them without each architect re-deriving them.

## Proposal
Defaults that devkit's devshell (Nix/direnv and devcontainer) sets, each overridable per repo and per host:
- `CARGO_BUILD_JOBS=2`, nextest `--test-threads 2` (via `.config/nextest.toml` profile), nix `--cores 2 --max-jobs 1` for in-shell builds.
- `CARGO_TARGET_DIR` under a host-registered build root (configured by the host, e.g. an env var the host sets), never ad-hoc temp dirs, so cleanup can be scoped per project without age-based sweeps.
- `CARGO_INCREMENTAL=0` for agent shells (incremental caches grew to 20+ GB per worktree).
- A preflight helper (`just preflight` or similar) that refuses a heavy step when free space on the *destination* volume is below a threshold (start above 25 GiB, stop below 15 GiB) and prints the largest build dirs once.

## Pitfalls
- Hard-coding host paths in the kit: the build root must come from the host.
- Overriding a repo's explicit settings: the defaults must yield to repo config.
- macOS vs Linux `df` differences in the preflight.

## Acceptance
- A fresh repo scaffolded from devkit gets these variables in its devshell, documented in its README.
- The preflight exits non-zero below the threshold, with a test.
- Repo- and host-level overrides are documented.

