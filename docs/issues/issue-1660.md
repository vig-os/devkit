---
type: issue
state: open
created: 2026-09-21T06:43:46Z
updated: 2026-09-21T07:42:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1660
comments: 2
labels: feature, priority:medium, area:ci, area:workspace, effort:large, semver:minor
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-21T07:52:31.809Z
---

# [Issue 1660]: [[FEATURE] Ship actionlint to consumers: the workflow-lint hook plus a managed actionlint.yaml config](https://github.com/vig-os/devkit/issues/1660)

> **Rescoped twice.** Originally "hold the `ubuntu-26.04` bump" (devkit-only);
> then "ship a managed `actionlint.yaml`". Investigation showed the config alone
> is dead weight — **no consumer runs `actionlint` at all** — so the scope is now
> the capability that makes it worth having: ship the workflow-lint **hook** to
> consumers, with the config as its enabler. The corrected findings are in
> [Diagnosis](#diagnosis); one claim in the previous revision was wrong and is
> retracted there.

### Chore Type

CI / Build change

### Description

`actionlint` has been in the vigOS toolchain since #995 — `nix/devtools.nix:63`,
so it is on `PATH` in the dev-shell, the image, and the `vigos.packages` home
module — but the prek hook that runs it is deliberately devkit-only
(`.pre-commit-config.yaml` L103–L107). Consumers therefore ship GitHub Actions
workflows that **nothing ever lints**: verified zero `actionlint` hooks across
`vig-os`, `exo-pet`, `MorePET` and `exoma-ch`, and no CI or `justfile`
invocation anywhere.

That is the gap worth closing. `shellcheck` is the exact precedent: same
toolchain SSoT (`nix/devtools.nix:48`), same `language: system` form, and it
already ships to consumers (consumer template L79). `actionlint` is no harder to
deliver than a hook the scaffold has shipped for releases.

Shipping the hook creates a second requirement. `actionlint` rejects any
**literal** `runs-on:` label absent from its built-in list, and a repo cannot
teach it one without an `actionlint.yaml` declaring `self-hosted-runner.labels`.
Two label sources matter:

1. **Hosted labels the built-in list lags.** `ubuntu-26.04` is a live runner —
   PR #1658's `Build Container Image` job ran on `Image: ubuntu-26.04` /
   `20260907.131.1` and passed — but `actionlint` v1.7.12 does not know it.
   v1.7.12 is the **latest upstream release, published 2026-03-30**, months
   before that image shipped, so no pin bump closes it. #1658 bumps the scaffold
   templates too, so consumers would render a literal `ubuntu-26.04`.
2. **Self-hosted labels, only where they appear literally.** See the retraction
   in Diagnosis — this is narrower than the previous revision claimed, and is not
   on its own a justification.

So: hook + config + the knobs to opt out of both and to extend the label list.

**Trade-off to accept explicitly:** a label in `self-hosted-runner.labels` is a
label `actionlint` will no longer flag as a typo. The list stays minimal — the
labels the scaffold actually renders — and shrinks when upstream catches up.

### Diagnosis

**Retraction.** The previous revision claimed `DEVKIT_CI_RUNNER` gives consumers
an unfixable `runner-label` failure. That is **false**, verified three ways:

- `actionlint` flags only *literal* labels. `runs-on: ${{ fromJSON(...) }}` is
  skipped entirely — tested directly: a literal `meatgrinder` errors, the
  `fromJSON` form produces nothing.
- `DEVKIT_CI_RUNNER` reaches `runs-on` **only** through that expression
  (`assets/workspace/.github/workflows/ci.yml` L210/251/292/442/512/599), so its
  labels are invisible to `actionlint`.
- Only one repo sets the knob — `exo-pet/exo-fleet`
  (`self-hosted,linux,x64,ci-vm`) — and it is unaffected for that reason.

Self-hosted labels still matter once a consumer writes one **literally** in a
workflow of their own, which the hook would newly lint. That is a real case, just
not the standing breakage previously described.

**Measured on PR #1658 head `8da4317e`** (run `35549998329`, job
`106182834232`, step 3):

- 43 `[runner-label]` findings across 19 devkit workflows: 42 × `ubuntu-26.04`,
  1 × `ubuntu-26.04-arm`. Reproduced locally at 43/43.
- `actionlint` was the **only** failing prek hook; the other 30 passed.
  `Test Summary` is the aggregator echoing `Project Checks: failure`.
- The composite `test-project` action runs `bats tests/bats/` in the *same* shell
  step as `prek run --all-files` under `set -euo pipefail`, so prek's exit 1
  aborted the step before bats ran. The bats suite fails too — all 7 `actionlint`
  tests over the rendered templates.

A `.github/actionlint.yaml` was then tested in a throwaway worktree at that commit:

| Target | Result |
|---|---|
| devkit's own 19 workflows | ✅ exit 0 |
| smoke templates (linted by path from `$PROJECT_ROOT`) | ✅ bats test 7 passes |
| the 6 rendered-mode bats tests | ❌ still fail |

The six rendered tests `cd` into a freshly `git init`'d temp workspace and run
bare `actionlint`, so a devkit-root config is invisible there — the same reason a
real consumer repo needs its own copy.

### Acceptance Criteria

**The hook**

- [ ] `assets/workspace/.pre-commit-config.yaml` ships an `actionlint` hook in the
      `shellcheck` idiom: `repo: local`, `language: system`, `entry: actionlint`,
      `files: ^\.github/workflows/.*\.ya?ml$`, `pass_filenames: false`
- [ ] The hook passes on a freshly scaffolded workspace in every mode
      (devcontainer, direnv, bare, both) and under both workflow models
- [ ] Adoption path for existing consumers decided and implemented (see the open
      question below) — `.pre-commit-config.yaml` is in `PRESERVE_FILES`, so a new
      hook does **not** reach an existing repo on upgrade

**The config**

- [ ] `assets/workspace/.github/actionlint.yaml` ships as a managed template
      rendering `self-hosted-runner.labels`
- [ ] Baseline labels carry their reason inline, so a later reader knows when to
      delete one; the list stays in lockstep with what the scaffold renders
- [ ] New knob `DEVKIT_ACTIONLINT_LABELS` (comma-separated, whitespace-tolerant,
      empty default) appends labels, validated and round-tripped to `.vig-os`
      like `DEVKIT_FEATURES_DISABLED`
- [ ] Labels named by `DEVKIT_CI_RUNNER` are included automatically — that knob
      is already their SSoT — so a consumer who writes one literally is covered
      without restating it
- [ ] Consumer override: `.github/actionlint.yaml` in `PRESERVE_FILES`, same class
      as `.yamllint` / `.pymarkdown` / `.typos.toml`, with
      `print_preserved_template_diff` keeping template evolution visible

**Opt-out**

- [ ] A new `actionlint` group in `DEVKIT_FEATURES_DISABLED` disables **both**
      halves: the config via `feature_paths()` copy-exclude + prune, and the hook
      via a render-time conditional (a hook inside a preserved file cannot be
      path-pruned — `.pre-commit-config.yaml` is already knob-rendered, cf.
      `--refs-optional-types`, so the block is omitted at render)
- [ ] Validation error-message subset list updated; preview classification correct
- [ ] Empty/absent knobs leave existing consumers byte-identical apart from the
      new file

**devkit itself + gates**

- [ ] devkit's own `.github/actionlint.yaml` added (its workflows are not scaffolded)
- [ ] `actionlint` over `.github/workflows/` passes on devkit with #1658 applied
- [ ] All 7 `actionlint` bats tests pass in every mode
- [ ] New bats coverage: hook present/absent per opt-out, default config render,
      `DEVKIT_ACTIONLINT_LABELS` append, `DEVKIT_CI_RUNNER` derivation, feature
      opt-out + prune, preserved-file override, manifest write-back
- [ ] TDD per repo rules: failing test committed before implementation
- [ ] `docs/MIGRATION.md` knob rows + a section, `.vig-os` comment block,
      `CHANGELOG.md` `## Unreleased`
- [ ] #1658 rebased/re-cut and merged with both gates green

### Implementation Notes

Target files: `assets/workspace/.pre-commit-config.yaml`,
`assets/workspace/.github/actionlint.yaml` (new), `.github/actionlint.yaml` (new),
`assets/init-workspace.sh`, `assets/workspace/.vig-os`,
`tests/bats/init-workspace.bats`, `docs/MIGRATION.md`, `CHANGELOG.md`.

`assets/init-workspace.sh` touch points: knob read (~L346), validation
(~L460–L520), `feature_paths()` (~L1602), `PRESERVE_FILES` (~L73), a render
function, write-back (~L3202). `render_license()` (#1651, ~L1548) is the closest
structural precedent, including its three-state write logic — already-our-output
→ silent no-op; absent or stock copy → render; anything else → consumer-owned,
leave with a notice — and the `chmod u+w` the read-only `/nix/store` assets need.

**Open question — adoption for existing consumers.** `.pre-commit-config.yaml` is
preserved (#878/#913/#1099), so an upgrade never adds the hook to an existing
repo. Three candidates:

1. **New repos only.** The #878 `print_preserved_template_diff` surfaces the new
   hook on upgrade and the consumer folds it in. This is what the #1652 table's
   own comment says is correct: that table is for blocks the template *retired
   because they break* — "never for ordinary drift" — and it names the #878 diff
   as "the right tool for 'a new hook was added'". Cheapest, and consistent with
   the documented split.
2. **Append-repair**, the #877 pattern used for `justfile.project` base recipes:
   detect the missing hook and append it from the template. Actually lands the
   hook everywhere, at the cost of writing into a file the consumer owns.
3. **Hook ships disabled**, consumer opts in via the knob. Safest rollout, but it
   means the capability is off by default in every existing repo.

(1) is the documented default and (2) is the only one that actually delivers
linting to existing repos; worth settling before implementation, since it changes
both the code and the risk.

Second open point: whether a consumer whose preserved config *has* the hook but
whose `.github/actionlint.yaml` is stale deserves a signal. The #1652 known-bad
table is explicitly not for this; the #878 diff covers it.

### Related Issues

Blocks #1658. Builds on `actionlint` adoption #995 and its shellcheck integration
#1003. Mechanisms reused: feature opt-outs #1284, preserved lint configs
#878 / #913 / #1099, preserved-file repair #877, knob + managed-file precedent
#1651, known-bad blocks #1652, `DEVKIT_CI_RUNNER` #1173. Prior runner bump: #544.

### Priority

Medium

### Changelog Category

Added

### Additional Context

`actionlint` in the current toolchain is `1.7.12` (`nix/devtools.nix`), with an
`overrideAttrs`'d variant for the image (`flake.nix`, #1107). All measurements
above were taken in a throwaway worktree at PR #1658 head `8da4317e`, since
removed.

Consumer survey (2026-09-21): `.pre-commit-config.yaml` carries no `actionlint`
hook in any repo of the four orgs; `DEVKIT_CI_RUNNER` is set only in
`exo-pet/exo-fleet`.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 21, 2026 at 07:23 AM_

Adoption path decided: **option 1 — new repos only**.

The hook ships in the scaffold template; existing consumers receive it through the #878 `print_preserved_template_diff` on upgrade and fold it in by hand. This follows the split the #1652 table's own comment documents — that table is for blocks the template retired *because they break*, "never for ordinary drift", and it names the #878 diff as the right tool for "a new hook was added".

No append-repair (#877 pattern) and no ships-disabled variant. The corresponding acceptance-criteria line is settled; the second open point (a stale `.github/actionlint.yaml` in a repo whose preserved config *has* the hook) stays covered by the same #878 diff.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 21, 2026 at 07:42 AM_

Scope reduction after the preserved-file decision landed (commits `bc4e9614`, `473084d6`).

`.github/actionlint.yaml` is now a **preserved** file — the consumer owns it, upgrades never overwrite it, and it carries the "yours to edit" banner. That makes two planned knobs redundant:

- **`DEVKIT_ACTIONLINT_LABELS` — dropped.** A preserved file is not re-rendered on upgrade, so the knob would apply only at first scaffold and silently do nothing afterwards. The consumer edits the file directly instead, which is the whole point of preserving it.
- **`DEVKIT_CI_RUNNER` label derivation — dropped.** Those labels reach `runs-on` only via `${{ fromJSON(...) }}`, which actionlint never inspects. The only case needing a declaration is a literal label the consumer writes themselves, in a file they already own.

The alternative that would have justified both — a *managed* file with the #1640 `render_refs_policy` anchored-idempotent-sed pattern, knob as sole override — was rejected: it contradicts consumer overriding by direct edit and adds machinery for no gain.

Still in scope: the `actionlint` group in `DEVKIT_FEATURES_DISABLED` (opt out of shipping it at all), docs, changelog, and the #1658 rebase. The corresponding acceptance-criteria lines are superseded by this comment.

