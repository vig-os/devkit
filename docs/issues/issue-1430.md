---
type: issue
state: closed
created: 2026-08-12T01:05:44Z
updated: 2026-08-12T07:32:05Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1430
comments: 2
labels: feature, priority:medium, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:43.687Z
---

# [Issue 1430]: [A fresh clone does not enforce devkit's own commit rules until scripts/init.sh runs](https://github.com/vig-os/devkit/issues/1430)

## What happened

Building the Rust language pack (#1400 / #1429) I did a plain `git clone` of devkit and started committing. My first two commits **violated two of devkit's own mandatory rules and were accepted**:

- branch `feat/rust-language-pack` — the taxonomy is `<type>/<issue>-<summary>` and `feat` is not a valid type (`feature` is)
- `Refs #1400` — the standard requires the trailer `Refs: #1400`, colon included

Neither was caught. They surfaced only on my *third* commit, by which point something in the session had run `scripts/init.sh` and the hooks became live. Then a push was additionally rejected by the signed-commits ruleset, which is the only one of the three that is enforced server-side.

## Root cause

`.githooks/` is tracked, so a fresh clone *has* the hook shims on disk. But git does not use them until `core.hooksPath` points there, and the only thing that sets it is `scripts/init.sh:203`:

```sh
if git config core.hooksPath .githooks && chmod +x .githooks/* 2>/dev/null; then
```

`core.hooksPath` is **local repo config**, so it is not cloned and cannot be. Between `git clone` and `scripts/init.sh`, devkit's entire commit-side gate stack is present, believed active, and inert. Nothing says so.

## Why this matters more than it looks

This is the same failure class the Rust pack exists to prevent, occurring in the tool that defines the standard. From the first consumer's history (`gerchowl/filesender`), **five separate things** were configured, believed active, and never executed — a `deny.toml` outside the build fileset banning nothing, a `clippy.toml` the sandboxed clippy never read, `.pre-commit-config.yaml` entries at the wrong indent, hook commands absent from `PATH`, and a `just precommit` recipe that ran only the pre-commit stage so the whole gate suite never ran in CI. Every one was invisible to inspection and obvious on execution.

Add this one: **the hooks are not installed until someone runs the installer, and nothing tells you.**

The population that hits it is not the edge case. Anyone who clones outside the devcontainer, any CI job that does not call `init.sh`, and — increasingly — any coding agent, which reaches for `git clone && git commit` and has no reason to know an installer exists.

Worth noting the failure is silent in the *dangerous* direction: an un-hooked clone lets bad commits through, rather than blocking good ones. There is no feedback signal at all.

## Options

Not a recommendation — the tradeoffs are devkit's to weigh:

1. **A tracked `.githooks/`-independent trip-wire.** Hard, given `core.hooksPath` is exactly the thing not yet set.
2. **Server-side rulesets for what is currently client-only.** Branch naming and the `Refs:` trailer are both mechanically checkable in a required status check. Signed commits already works this way, and it is the only one of the three that actually held. Strongest option — it does not depend on local state at all.
3. **Make `init.sh` unmissable**: a `CONTRIBUTING.md` first line, and a `just` default recipe that fails loudly when `core.hooksPath` is unset.
4. **A CI job asserting the config**, so an un-initialised clone fails the PR rather than the commit.

(2) and (4) are the ones that survive a contributor who never reads anything, which is the case that produced this issue.

## Acceptance

- [ ] Branch-name and `Refs:` conformance enforced somewhere that does not depend on local git config
- [ ] An un-initialised clone gets a loud signal before its first commit lands, not after
- [ ] `docs/` states plainly that `.githooks/` being tracked does **not** mean the hooks run

Refs: #1400, #1429

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 06:18 AM_

Triage against the current tree (dev @ae8baada), with the maintainer's decision on where the fix lands:

## What is already covered today

- **`Refs:` / commit-format conformance is already enforced independent of local git config**: CI's Commit Messages lane (`validate-commit-range`) walks `base..head` on every PR and validates each commit message plus the PR title. The `Refs #1400` (missing colon) commit would have failed PR CI — it simply hadn't reached a PR yet. Acceptance bullet 1 is therefore half-met; the un-met half is the **branch name**, which today has no gate anywhere outside the local hook.
- **Both sanctioned environments auto-wire `core.hooksPath` on entry**, no installer needed: the devcontainer via `setup-git-conf.sh`, and the dev-shell via `mkProjectShell`'s `githooksPathHook` (#1112) — which includes **devkit's own repo**, whose `devShells.default` is `mkProjectShell` (flake.nix). A fresh clone + `direnv allow`/`nix develop` has live hooks before the first commit. The incident window is precisely *bare clone + commits from a bare shell + no PR yet* — and the local half of that window is unfixable by construction, as the report itself notes (`core.hooksPath` is exactly the thing that cannot be tracked).
- **The docs caveat exists**: `docs/COMMIT_MESSAGE_STANDARD.md` (synced into every scaffold) states the guard "is only silently absent before you have entered [the sanctioned environment]". Bullet 3 residue is a pointer in the contributor-facing entry docs, not a new statement.

## Decision: the enforcement gap closes in #1432 (milestone 1.7.1)

Option 2/4 — the only class that survives "a contributor who never reads anything" — is being folded into #1432 (`DEVKIT_BRANCH_TYPES`), which is already threading the branch-type set through `resolve-toolchain`: a **branch-name check in CI's commit-checks lane** validating the PR head ref against the same single source of truth the local hook renders from. Doing it inside #1432 (rather than as a follow-up) keeps the knob and the CI gate in lockstep from day one — the #1074 desync class is the reason these gates are driven from one key.

Design notes for that gate, so the tradeoffs are on record:
- The head ref is validated via env routing (never inline `${{ }}`), types driven by `resolve-toolchain`'s resolved list (so `DEVKIT_BRANCH_TYPES` steers CI and the local hook identically).
- The allowed set is a **superset** of the local hook's: automation branches that legitimately open PRs but never run local hooks must pass — `release/X.Y.Z` (every release PR), `renovate/*` (#1433), `worktree/<n>`, plus whatever the scaffolded automation creates (inventoried as part of the change).
- Devkit's own bespoke `ci.yml` gets the same step, so the repo that defines the standard enforces it on itself — the case this issue reported.

## What remains here after #1432

This issue stays open as the umbrella for the small residue: a CONTRIBUTING/README first-line pointer in devkit itself, and optionally a loud `just` default-recipe warning when `core.hooksPath` is unset. Both cheap, neither train-blocking.

Refs: #1432

---

# [Comment #2]() by [c-vigo]()

_Posted on August 12, 2026 at 07:32 AM_

Closed by #1438, merged to `dev` as 31b0f191.

All three acceptance boxes are now satisfied. Two were already closed by earlier work and were re-verified against the code rather than reimplemented:

- [x] **Branch-name and `Refs:` conformance enforced somewhere that does not depend on local git config** — the `commit-checks` job validates the PR head ref (`.github/workflows/ci.yml:304`, the gate folded into #1432, whose comment names this issue) and runs `validate-commit-range` over `merge-base(base, head)..head` plus the PR title (`.github/workflows/ci.yml:330`). Both run on GitHub-side clones and read nothing from local git config. The pair reported here — branch `feat/rust-language-pack` and trailer `Refs #1400` — fails both gates: `feat` is not in the type set and carries no issue number, and the missing colon is rejected by the validator.
- [x] **An un-initialised clone gets a loud signal before its first commit lands, not after** — implemented in #1438. `just doctor` now reports the `core.hooksPath` state, distinguishing the two failure modes:

  ```
  PASS git hooks: core.hooksPath -> .githooks
  WARN git hooks: core.hooksPath not set, .githooks is tracked but inert (run: ./scripts/init.sh)
  WARN git hooks: core.hooksPath=<value>, expected .githooks (run: ./scripts/init.sh)
  ```

  `doctor` stays diagnostics-only and still always exits 0. Covered by three tests in `tests/bats/doctor.bats`.
- [x] **`docs/` states plainly that `.githooks/` being tracked does not mean the hooks run** — `docs/COMMIT_MESSAGE_STANDARD.md:95`, mirrored to consumers at `assets/workspace/docs/COMMIT_MESSAGE_STANDARD.md:98`.

On the options weighed in the issue: (2) and (4) — enforcement that survives a contributor who never reads anything — are what actually closes the gap for the reported population, and those landed via the CI gate. The `doctor` diagnostic is (3), and it is deliberately pull-based: it serves the person who is looking, while CI holds the line for the person who is not. No hard local gate was added.

Two follow-ups noted but deliberately not implemented here, as neither is a #1430 fix:

1. The scaffolded consumer surface ships no `doctor` equivalent, so a consumer clone gets no host preflight at all. That is a new consumer-facing recipe needing its own manifest/sync and coverage.
2. `PASS` is an exact match on the literal `.githooks`; an equivalent absolute path would `WARN`. Correct today, since `scripts/init.sh:203` only ever writes the relative value.

Shipping in the 1.8.0 train.

