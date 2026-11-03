---
type: issue
state: open
created: 2026-10-04T15:22:10Z
updated: 2026-10-04T15:22:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1811
comments: 0
labels: bug, priority:high, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-05T08:48:21.493Z
---

# [Issue 1811]: [Rust pack: CI Tests and Lint lanes run no Rust and report green](https://github.com/vig-os/devkit/issues/1811)

## Description

In a repo scaffolded with the Rust language pack (devkit 1.17.0, `DEVKIT_LANGUAGES=rust`), CI's
**Tests** and **Lint & Format** lanes run **no Rust at all** and report green.

Seen in `vig-os/stepv` (PR #15, run 37210657329). The Tests job log says, verbatim:

```text
just sync: no pyproject.toml — skipping
just test: no pyproject.toml — skipping
```

## Why

- `ci.yml`'s `test` job runs `just test`, and the scaffolded `justfile.project` `test` recipe is
  **pytest-only**: with no `pyproject.toml` it prints a skip line and exits 0.
- `ci.yml` never runs `nix flake check`, so the `checks` that `mkRustProject` builds (fmt, clippy,
  nextest, doctest, doc) are never run in CI.
- The Lint lane runs `just precommit`, and the flake-generated hook set has no rustfmt or clippy
  hook either.

The language gate (`DEVKIT_LANGUAGES` marker-file check) only proves `Cargo.toml` **exists**. It
doesn't prove anything ran. That is the "green check over nothing" the gate was meant to
prevent (#1478 / #1281 lineage).

## Proposed solution

Either:

- have the Rust pack render a Cargo-aware `test`/`lint` (cargo nextest + clippy `-D warnings` +
  `fmt --check`); or
- have `ci.yml` run `nix flake check` (or `nix build .#checks.<system>.*`) when the Rust pack is on.

Then make a skip line an **error** when `DEVKIT_LANGUAGES` declares a language the recipe didn't
run.

## Workaround in stepv

`justfile.project`'s `test`/`lint` now run the Rust suite when `Cargo.toml` exists (vig-os/stepv#17).

