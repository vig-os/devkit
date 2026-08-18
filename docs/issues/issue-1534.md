---
type: issue
state: closed
created: 2026-08-17T09:28:19Z
updated: 2026-08-17T13:26:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1534
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:14.039Z
---

# [Issue 1534]: [[BUG] Synced devkit changelog breaks typos in devcontainer-mode consumers with pre-#1488 seeds](https://github.com/vig-os/devkit/issues/1534)

## Description

Residual exposure of the #1529 class, found while building the #1531 lint guard (see `tests/bats/release-mirror-fold-lint.bats` header).

Devkit's own `CHANGELOG.md` is synced verbatim into the scaffold at
`assets/workspace/.devcontainer/CHANGELOG.md` (`scripts/manifest.toml:61-62`),
and devcontainer-mode consumers **git-track** that file (devkit-smoke-test
tracks 23 `.devcontainer/` files). The **released** 1.10.0 section contains
`mis-parses` / `mis-splitting` (currently `CHANGELOG.md:170,172`) — text that
is immutable under the changelog rules, and only spell-clean under a
`.typos.toml` carrying #1488's `mis = "mis"`.

A devcontainer-mode consumer whose seeded `.typos.toml` predates #1488 would
therefore fail its upgrade at the commit step exactly like #1529 — and neither
of the two consumer-side config files can deliver a fix, because **both**
`.typos.toml` **and** `.pre-commit-config.yaml` are preserved (seeded once,
never overwritten; `assets/init-workspace.sh:107`).

## Blast radius

Nobody today: the only devcontainer-mode consumer is `devkit-smoke-test`
(`DEVKIT_MODE=both`) and its seed already has `mis`; every other consumer is
`direnv` mode and tracks zero `.devcontainer/` files. This is why the #1531
guard renders `direnv` mode only and deliberately excludes this file.

## Options

1. **Sanitize at sync**: `scripts/manifest.toml` already supports `Sed`
   transforms on this dest — rewrite the offending tokens in the synced copy
   (the dest is a generated artifact; the released source stays untouched).
2. **Prevent recurrence at the source**: lint `CHANGELOG.md` *Unreleased*
   additions typos-clean with **no allowlist** in devkit CI, so no future
   release can freeze a seed-dependent token into immutable text (catching it
   after release is useless — released entries may never be edited).
3. **Stop syncing the changelog** into the consumer worktree — check what
   consumes it (`version-check.sh`?) before considering.

(1) fixes the existing 1.10.0 text, (2) stops the class; they compose. (3) is
the heaviest and probably unwanted.

## Acceptance

A devcontainer-mode render with a pre-#1488 seed (or the #1531 guard extended
with a devcontainer-mode leg, no allowlist) passes `typos` over the tracked
tree, including `.devcontainer/CHANGELOG.md`.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 01:26 PM_

Fixed in #1543 (merged to dev), sanitize + guard as planned: (1) manifest Sed transforms de-hyphenate the immutable 1.10.0 tokens in the generated .devcontainer/CHANGELOG.md only (misparses/missplitting, verified clean under typos --isolated; source untouched, idempotent by construction); (2) new runner-only check-unreleased-typos hook (nix/hooks.nix SSoT) lints the Unreleased changelog section with no allowlist so no future release can freeze a seed-dependent token; (3) release-mirror-fold-lint.bats gained the devcontainer-mode acceptance leg, linted with a frozen pre-#1488 grandfather list (Nd ba passt unexcepted) that encodes the invariant: generated content may not depend on allowlist entries newer than a consumer's seed. Tokens still failing a strict tree-wide no-allowlist lint are enumerated in the PR body should a fully allowlist-free tree ever be wanted.

