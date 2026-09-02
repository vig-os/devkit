---
type: issue
state: open
created: 2026-09-02T06:21:48Z
updated: 2026-09-02T06:21:48Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1601
comments: 0
labels: chore, priority:medium, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-02T07:01:32.808Z
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

