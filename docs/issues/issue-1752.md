---
type: issue
state: open
created: 2026-09-28T12:58:17Z
updated: 2026-09-28T12:58:17Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1752
comments: 0
labels: feature, priority:medium, area:ci, area:workspace, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:53.709Z
---

# [Issue 1752]: [feat(scaffold): knob to advance a PINNED devkit flake input on upgrade, plus a CI guard for scaffold/toolchain skew](https://github.com/vig-os/devkit/issues/1752)

## Problem

In `direnv`/`bare` mode the scaffold and the toolchain are versioned **twice**, and
an upgrade only moves one of them:

| Number | Where | Governs |
|---|---|---|
| `DEVKIT_VERSION` | `.vig-os` | the scaffold — `ci.yml`, `release-core.yml`, hook config, justfiles |
| the devkit flake input's ref | `flake.nix` (a `PRESERVE_FILE`) | the tools those workflows call — `vig-utils`, `pymarkdown`, the overlay |

`install.sh`'s flake-bump block (#1263, name-agnostic since #1497) advances the
**lock** for a *floating* input, and deliberately declines for a **pinned** one:

```
flake-bump: skipped — input 'vigos' is pinned to '1.6.0' (your explicit choice; never auto-bumped)
```

That default is right — a pin should not be silently rewritten. But it leaves a
pinned consumer with a two-step upgrade whose second step is enforced by nothing,
and in `direnv` mode the flake input is the **only** source of devkit's tools
(`resolve-toolchain` emits an empty image, `setup-devkit-toolchain` runs
`nix develop` on the consumer's flake). So a forgotten pin bump means CI and every
developer run the *previous* release's tools against the *new* scaffold.

### This is not theoretical

Observed upgrading `vig-os/scitadel` 1.6.0 → 1.17.0
([vig-os/scitadel#225](https://github.com/vig-os/scitadel/issues/225)):

- `prepare-changelog` subcommands at **1.6.0**: `finalize prepare reset reset-version unprepare validate`
- at **1.17.0**: adds **`seed`**
- the 1.17.0 scaffold's `release-core.yml` **calls `prepare-changelog seed`**

Scaffold at 1.17.0 + flake pinned at 1.6.0 ⇒ `invalid choice: 'seed'`, and it
surfaces **mid-release**, after the release branch is cut. The installer's warning
was the only thing standing between that and a green merge.

### Why the existing warning is not enough

The warning is printed once, at scaffold time, into a terminal log. Merge an
adoption PR without acting on it and nothing ever mentions it again — all three
plausible guards miss it **by construction**:

- **`scaffold-drift`** re-runs the scaffold and diffs managed files. `flake.nix` is
  a `PRESERVE_FILE`, so the regenerated tree contains the consumer's copy
  unchanged — the gate cannot see the pin at all.
- **`devkit-staleness`** compares `DEVKIT_VERSION` against the latest devkit
  release. At the new version it reports "current" and passes, whatever the flake says.
- No hook checks it.

Note also that **floating is not a fix** for a consumer that depends on stability:
since #1676's release-neutral lane, `main` legitimately carries landed-but-unshipped
changes (`origin/main` is 2 commits past `1.17.0` as I write this), so floating
trades "tools behind scaffold" for "tools ahead of scaffold" — *and* removes the only
comparable version token, making the skew undetectable rather than merely unchecked.

## Proposal A — a `.vig-os` knob (preferred)

```
# Advance a PINNED devkit flake input to DEVKIT_VERSION on upgrade: true | false.
# Empty (= unset) resolves to `false` — today's behaviour exactly, a pin is never
# rewritten. `true` opts in: an upgrade rewrites the pinned ref to the new
# DEVKIT_VERSION (preserving the pin FORM) and runs `nix flake update <input>`, so
# the scaffold and the toolchain move together. For consumers whose pin means
# "track DEVKIT_VERSION" rather than "hold this exact ref".
DEVKIT_FLAKE_PIN_ADVANCE=
```

Default empty ⇒ byte-identical to today for every existing consumer, matching the
house rule for new knobs.

### Why this is small

The pinned branch of the block already has everything in scope:

- `DEVKIT_INPUT_NAME` — the input name (name-agnostic, #1497)
- `DEVKIT_INPUT_URL` — the full URL
- `DEVKIT_PINNED_REF` — **already parsed**, via
  `sed -E 's|^github:vig-os/devkit[/?](ref=)?||'`, so **both** pin forms
  (`?ref=X` and the `/X` suffix) are already recognised

So the knob gates one surgical substitution of the ref token on the already-matched
one-liner, then reuses the existing `nix flake update` path — including its
non-fatal-on-failure handling and its single-`flake-bump:`-line contract, which the
adoption PR already surfaces.

### The one real objection, and the precedent

`flake.nix` is a `PRESERVE_FILE`, so devkit writing to it needs justification. Two
things make it defensible: the write happens **only** on the consumer's explicit
opt-in, and it is a single token on a line devkit already recognises by anchored
grep — not a regeneration. There is direct precedent: #1654 already performs
surgical inserts into the preserved `.pre-commit-config.yaml` (the `actionlint` and
`shellcheck-composite-actions` hook inserts), on the same reasoning.

Suggested guard rails: refuse and warn if the matched line is not a simple
one-liner; leave `flake.lock` advance non-fatal as today; print the outcome on the
existing `flake-bump:` channel so a declined or failed advance is never silent.

## Proposal B — infer intent instead of a knob

Advance a pin **only when it equals the OUTGOING `DEVKIT_VERSION`**. Such a pin
demonstrably tracks the manifest rather than holding a deliberate exact ref, so
advancing it cannot surprise anyone; a pin at any other value is left alone.

No new knob, and correct for the common case — but it is implicit, and a consumer
who genuinely wants to hold `1.6.0` while the manifest moves has no way to say so.
**Proposal A is preferable** for being explicit; B could be the default *for* A.

## Proposal C — the CI guard (complementary, and cheaper)

Worth doing **regardless of A or B**, since a consumer who opts out, or has not
upgraded yet, still gets no signal today.

Both halves are devkit-managed, so devkit can own this and **no consumer needs a
local copy**:

- `resolve-toolchain` already reads `.vig-os` (it has an explicit key allow-list and
  an outputs block, #1295) — have it also parse the flake input's ref and emit it
- `ci.yml` fails when a *pinned* ref ≠ `DEVKIT_VERSION`, and stays silent for a
  floating input (nothing to compare) and for `devcontainer` mode (no flake in play)

This turns "warned once in a log" into "cannot merge", which is the property the
coupling actually needs.

## Acceptance Criteria

- [ ] Empty/absent knob renders and behaves byte-identically to today
- [ ] `DEVKIT_FLAKE_PIN_ADVANCE=true` advances both `?ref=X` and `/X` pin forms,
      preserving the form, and leaves a non-devkit input untouched
- [ ] The knob round-trips across `--force` upgrades
- [ ] Every outcome (advanced / declined / failed / knob off) prints exactly one
      `flake-bump:` line, and the adoption PR surfaces it
- [ ] CI fails a PR whose pinned flake ref ≠ `DEVKIT_VERSION`; no false positive for
      a floating input or `devcontainer`/`bare`-without-flake modes
- [ ] `docs/MIGRATION.md` documents the knob and the invariant

## Refs

#1263, #1497 (flake-bump lineage) · #1654 (surgical edit of a preserved file) ·
#1295 (`resolve-toolchain` / drift gate) · #1676 (release-neutral `main`) ·
[vig-os/scitadel#225](https://github.com/vig-os/scitadel/issues/225) (where this was hit)
