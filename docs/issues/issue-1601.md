---
type: issue
state: closed
created: 2026-09-02T06:21:48Z
updated: 2026-09-02T08:11:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1601
comments: 3
labels: chore, priority:medium, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-03T07:05:16.433Z
---

# [Issue 1601]: [[CHORE] setup-devkit-toolchain: dev-shell gcroot lands in RUNNER_TEMP, so it never survives an ephemeral self-hosted job](https://github.com/vig-os/devkit/issues/1601)

### Description

`setup-devkit-toolchain` realises the consumer dev-shell into a profile under
`RUNNER_TEMP`:

```yaml
# .github/actions/setup-devkit-toolchain/action.yml
nix develop --profile "$RUNNER_TEMP/devkit-dev-profile" --command true
```

The `--profile` is what makes this a **gcroot** rather than a bare
`nix develop`, and on a hosted runner that is the right call — the root keeps
the closure alive for the remaining steps of the same job, and the machine is
discarded afterwards anyway.

On a **self-hosted runner with `ephemeral = true`**, the trade-off inverts.
`RUNNER_TEMP` is wiped at the end of every job, so the gcroot is destroyed
while the underlying nix store — the thing that makes a self-hosted runner
worth having — persists. The consequence is that the dev-shell closure is
unrooted between jobs and is collectable by the host's `nix.gc`, even though
every single CI run needs it.

Effect on a `DEVKIT_MODE=direnv` consumer with a heavy dev-shell, measured over
16 runs on a persistent-store self-hosted runner:

| `Set up devkit toolchain` | duration |
|---|---|
| warm store (p50) | **26 s** |
| after the store's periodic GC / after a flake input advance | **180–237 s** |

Three toolchain lanes (`lint`, `test`, `commit-checks`) run per CI run, so the
step is paid three times per run.

The store's own garbage collection is the failure mode: because nothing roots
the profile between jobs, a routine `nix-gc` on the runner discards the
dev-shell closure and the next run re-realises it from scratch. A self-hosted
runner is supposed to make that cost a one-off.

### Proposed change

Let the profile path be **configurable**, defaulting to today's behaviour so
hosted consumers are unaffected:

- add an optional input, e.g. `dev-profile-path`, defaulting to
  `${RUNNER_TEMP}/devkit-dev-profile` (no change for anyone today)
- a self-hosted consumer sets it to a persistent, runner-writable path so the
  gcroot survives across ephemeral jobs and the step becomes a near no-op

Alternatively the action could detect a self-hosted runner
(`RUNNER_ENVIRONMENT != 'github-hosted'`) and pick a persistent default itself,
but an explicit input is the safer contract — the action cannot know that a
given self-hosted runner has a persistent store, or that the path it picks is
writable and outside the workspace.

Either shape benefits **every** direnv-mode consumer on a self-hosted runner,
not just the one that reported it.

### Files / modules in scope

- `.github/actions/setup-devkit-toolchain/action.yml` (and the scaffolded copy)
- whatever test asserts the `extra_nix_config` / `Configure host Nix` lockstep,
  extended to cover the new input's default

### Out of scope

- The Cachix wiring in the same action — orthogonal, and it does not help here:
  a substituter round-trip is not a substitute for not deleting the closure.
- Hosted-runner behaviour, which must stay byte-identical by default.

### Invariants / constraints

- Default behaviour unchanged for every existing consumer (hosted and
  self-hosted alike) — the new input is opt-in.
- The action must not assume the configured path exists or is writable; a bad
  value should fail loudly at the step, not silently fall back to a
  non-persistent profile (a silently non-persistent gcroot is exactly the
  present bug).
- No change to the resulting `GITHUB_PATH` export or the dev-shell contents.

### Acceptance criteria

- [ ] With the input unset, the realised profile path is byte-identical to today
- [ ] With the input set to a persistent path, the profile survives a job
      boundary on an ephemeral self-hosted runner and survives a
      `nix-collect-garbage` on the runner host
- [ ] Second and subsequent runs on a warm self-hosted store complete the step
      without re-realising the dev-shell closure
- [ ] Documented in the action's input table with the self-hosted rationale

---

# [Comment #1]() by [c-vigo]()

_Posted on September 2, 2026 at 07:26 AM_

Recommendation on the wiring shape: make the knob a **`.vig-os` key** (e.g.
`DEVKIT_DEV_PROFILE_PATH`), routed through `resolve-toolchain` into the
proposed `dev-profile-path` input — rather than an input a consumer would have
to plumb via an Actions variable.

`DEVKIT_CI_RUNNER` is the exact precedent: same class of self-hosted-runner
infrastructure detail, declared in the consumer repo's committed manifest,
resolved by `resolve-toolchain`, and injected into the managed workflow
without any hand-edit of a scaffold-drift-protected file. It also needs no
repo variable / org-config declaration, round-trips across `--force`
upgrades by the persisted-values mechanism, and keeps the empty default
(= today's `${RUNNER_TEMP}` behaviour) byte-identical for every existing
consumer — hosted and self-hosted alike.

Two implementation notes for the issue's invariants:

- **Multiple ephemeral runner slots on one host will share the configured
  path.** That is fine — `nix develop --profile` goes through the normal
  profile-update lock, and concurrent identical realisations converge on the
  same generation — but the action's docs should say the path is expected to
  be shared and must sit on the same filesystem as the store's gcroot
  indirection expects (a local persistent dir, not a per-job tmpfs).
- The fail-loudly constraint composes naturally here: `resolve-toolchain` can
  refuse a relative path or one under `RUNNER_TEMP`/`GITHUB_WORKSPACE` at
  resolve time, before any lane pays the realisation cost.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 2, 2026 at 07:58 AM_

Shipped to `dev` in #1603 (merged 2026-09-02), wired as the comment recommended — a `.vig-os` key routed through `resolve-toolchain`, not an Actions variable.

**What landed**

- `DEVKIT_DEV_PROFILE_PATH` in `.vig-os`, shipped empty and persisted across `--force` upgrades by the installer's read-before-overwrite/write-back path — the same shape as `DEVKIT_CI_RUNNER`.
- `resolve-toolchain` reads the key and emits a `dev-profile-path` output, refusing at resolve time anything that could never persist: a relative path, a path inside the runner's `_work`/`_temp` tree, or the filesystem root. Trailing slashes are trimmed.
- `setup-devkit-toolchain` gains the optional `dev-profile-path` input, routed through `env:` (never inline `${{ }}` in `run:`). All four `nix develop` calls use the resolved value; the parent directory is created if possible and the step fails loudly if it cannot be created or written — the half only the target host can answer.
- `ci.yml` passes it in `lint`, `test` and `commit-checks`: exactly the lanes `DEVKIT_CI_RUNNER` can move onto a self-hosted host, and the three the report measured. Every other scaffolded job stays on the hosted default, where `RUNNER_TEMP` is the correct place for the root.
- `docs/MIGRATION.md` gains a *Keep the dev-shell gcroot across ephemeral self-hosted jobs* section plus the manifest-table row, carrying both implementation notes: runner slots on one host are expected to **share** the path (concurrent `nix develop --profile` realisations take the profile lock and converge), and it must be a local persistent directory, not a per-job tmpfs.

**Acceptance criteria**

- [x] Input unset => the realised profile path is byte-identical to today — pinned by an executed-bash test against the step's real `run:`.
- [ ] Profile survives a job boundary and a `nix-collect-garbage` on an ephemeral self-hosted runner — **not verifiable in this repo's CI**; needs a live run on a consumer with such a runner.
- [ ] Second and subsequent runs on a warm self-hosted store skip the re-realisation — same, wants the live measurement (the 26 s vs 180–237 s comparison) after adoption.
- [x] Documented in the action's input table with the self-hosted rationale, plus `.vig-os`, `ci.yml`'s header and `MIGRATION.md`.

The two open boxes are the reason to keep this in view at adoption: set `DEVKIT_DEV_PROFILE_PATH` on the reporting consumer once it takes the release carrying #1603, and compare the `Set up devkit toolchain` step duration across a `nix-gc` on the runner host. If it still re-realises, that is a new issue, not a reopen of this one.

Coverage: 27 tests — resolve-time emission and refusals executed against the action's real bash, six executed-bash cases on the step itself (default, override moving *every* realisation, relative/uncreatable/unwritable refusals), the manifest declaration and the upgrade round-trip.

One honest limit worth recording: the `_work`/`_temp` guard catches the mistake the knob exists to prevent — rooting inside the tree the runner clears — but it cannot prove an arbitrary path is persistent, and does not try to.

---

# [Comment #3]() by [c-vigo]()

_Posted on September 2, 2026 at 08:11 AM_

Field evidence from a direnv-mode consumer on a self-hosted ephemeral runner, after the runner VM was restarted (store intact, page cache cold):

| `Set up devkit toolchain` | duration |
|---|---|
| warm steady state (p50, n=16) | 26 s |
| first runs after the VM restart | **3 m 18 s**, **2 m 48 s**, **2 m 18 s** |

Three toolchain lanes run per CI run, so that is ~8 minutes of a single run spent re-realising a dev-shell whose closure never left the machine.

This is the cost the issue describes, in its most visible form: the store still had every path, but with the gcroot gone from `RUNNER_TEMP` the profile had to be re-realised from scratch rather than re-linked. A persistent profile path would have made these runs no different from the warm case.

