---
type: issue
state: open
created: 2026-10-16T15:07:53Z
updated: 2026-10-16T15:07:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1899
comments: 0
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-17T06:49:13.624Z
---

# [Issue 1899]: [Rust pack: the release train never sets the crate version (Cargo.toml/Cargo.lock) for X.Y.Z](https://github.com/vig-os/devkit/issues/1899)

Downstream: vig-os/vigil#151. `prepare-release.yml` freezes the CHANGELOG only. For a Rust consumer the crate's `[package].version` stays wherever dev has it (vigil: `0.0.0`), so a train-cut `X.Y.Z` tag ships a crate that reports another version (`cargo metadata`, `env!("CARGO_PKG_VERSION")`, and later crates.io).

vigil now does it in its project-owned `prepare-release-extension.yml` (vig-os/vigil#153). It mints COMMIT_APP like the freeze commit, verifies the head equals `branch_sha`, and runs a tested stdlib script that sets only `[package].version` and the root `Cargo.lock` entry, idempotently, honouring `dry_run`.

Proposal: the Rust pack does this itself, with a workspace-aware variant (`[workspace.package].version`), so every Rust consumer gets a correct version without a custom hook.
