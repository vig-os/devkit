---
type: issue
state: open
created: 2026-07-13T06:13:58Z
updated: 2026-07-13T10:11:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/988
comments: 5
labels: feature, priority:high, area:ci, area:workspace, effort:large, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: 989, 990, 991, 992, 993, 994, 995
synced: 2026-07-13T15:17:55.799Z
---

# [Issue 988]: [[EPIC] Mode-aware scaffold: CI/release toolchain per deployment mode](https://github.com/vig-os/devkit/issues/988)

### Description

Deploying the devkit to `vig-os` repos (rollout pilot: `commit-action`, `--mode direnv`)
revealed that the **CI and release layer of the scaffold is hard-coupled to the
devcontainer image regardless of the chosen `DEVKIT_MODE`.** Every scaffolded CI
and release job runs inside `container: ghcr.io/vig-os/devcontainer:<tag>` via the
`resolve-image` job; no workflow branches on mode. A repo that deliberately picks
`direnv` or `bare` to be container-free is therefore only half-honored: local dev
skips the container, but CI still mandates the image.

This epic makes the scaffold **honor the deployment mode end-to-end** while keeping
the release choreography single-source.

### The three axes (currently conflated)

| Axis | Answers | Correct granularity |
|------|---------|---------------------|
| **Deployment mode** (container/direnv/bare) | how a *developer* gets a local env | per-repo choice |
| **CI toolchain** | how *CI jobs* get their tools | should track the mode (today: always the container) |
| **Release artifact** | what the repo *ships* (image / JS action / crate / flake) | per **artifact type**, not per mode |

### Agreed design direction

- **One release pipeline, not three.** `release-core/publish/extension` are already
  reusable `workflow_call` workflows — the choreography (version bump, changelog
  finalize, tag, PR merge, draft release, rollback) stays single-source. Three
  per-mode copies are explicitly rejected (SSoT/DRY: triplicates the most fragile
  automation).
- **Mode-adaptive toolchain preamble.** A shared `setup-devkit-toolchain` composite
  action branches on `DEVKIT_MODE` from `.vig-os` (the same source `resolve-image`
  already reads): `container` → `container:` image; `direnv` → `install-nix-action`
  + `nix develop`; `bare` → host-native `setup-node`/`uv`/etc.
- **Publish step keyed on artifact type, not mode.** Image push vs `npm publish`/
  marketplace vs `cargo publish` is a small per-repo hook.
- Known awkward spot: GitHub's job-level `container:` key can't be conditionally
  unset by expression — needs `if:`-gated job wrappers or a documented
  "container unless mode≠container" default.

### Acceptance Criteria

- [ ] A `direnv`/`bare` consumer's CI and release run container-free (no forced
      `ghcr.io/vig-os/devcontainer` pull).
- [x] Release choreography remains single-source (no per-mode pipeline copies).
- [x] Scaffold stops shipping container-only artifacts into container-less modes (#D1).
- [x] Mode-switch migration path for a stale `.devcontainer/` is defined (#D2).
- [x] Mode-aware CI/release toolchain implemented (#D3).

### Sub-issues

- D1 — direnv/bare scaffold ships container-only artifacts
- D2 — mode-switch doesn't prune a pre-existing `.devcontainer/`
- D3 — CI + release workflows hard-coupled to the container image toolchain

### Additional Context

Surfaced by the devkit rollout pilot; blocks resuming deployment to `commit-action`
(vig-os/commit-action#29, also closes #30) and the other `vig-os` code repos.
Pilot preview was read-only — no consumer repos were modified.


---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 07:11 AM_

## Implementation plan (approved 2026-07-13)

### Scope corrections from research

The epic text says "no workflow branches on mode" — that is no longer accurate, which shrinks D3:

- **`ci.yml` is already mode-aware** via whole-file overlays (`assets/workspace-direnv/`, `assets/workspace-bare/`, applied by `init-workspace.sh`), with per-mode bats render assertions in `tests/bats/init-workspace.bats`.
- The actual gap is the **8 remaining container-coupled workflows** (13 jobs): `release.yml` (rollback), `release-core.yml` (validate/finalize/test), `release-publish.yml` (publish), `prepare-release.yml` (prepare + inline resolve-image), `promote-release.yml` (4 jobs), `sync-main-to-dev.yml` (2), `renovate-changelog-build.yml` (1), `sync-issues.yml` (1). Already host-safe: `release-extension.yml`, `renovate-changelog-commit.yml`, `codeql.yml`, `scorecard.yml`.
- **All three toolchain branches already exist as prototypes in-repo:** the devkit's own release choreography runs host+Nix via `.github/actions/setup-env` (install-nix + cachix + `nix develop --profile` + `GITHUB_PATH` export + `retry` shim via `BASH_ENV`) — the direnv branch at release scale. The bare branch prototype is `workspace-bare`'s `ci.yml` (`setup-uv` + `uv tool install`). The container branch is the status quo.
- **Hard host-mode blockers are three image-baked binaries:** `retry` (solved by the setup-env shim), and `prepare-changelog` / `renovate-changelog-pr` — console scripts of `packages/vig-utils`, baked into the image but **not** in `devTools`, so consumer dev-shells lack them today. `git`/`gh`/`jq` are free on hosted runners.
- Also container-coupled and to be absorbed into the mode branch: `UV_PROJECT_ENVIRONMENT=/root/...`, `PREK_HOME=/opt/prek-cache`, `safe.directory` steps, GHCR `container.credentials`.
- No `{{PLACEHOLDER}}` tokens exist in any workflow file — the sed substitution engine is untouched.

### Architecture

One release choreography + a shared **`setup-devkit-toolchain` composite action** branching on `DEVKIT_MODE` from `.vig-os`, using the `GITHUB_PATH`-export pattern from the devkit's own `setup-env` — after it runs, plain `run: just sync` works in every mode, so the ~2 000 lines of choreography steps stay untouched.

The composite cannot set job-level `container:`. Two resolutions, decided by a spike:

- **Option A — conditional container:** a first `resolve-toolchain` job reads `.vig-os` and outputs `mode` + `image` (empty unless container mode); jobs declare `container: image: ${{ needs.resolve-toolchain.outputs.image }}` (empty image = host). Single-source, container-mode byte-identical to today. Risk: empty-image-skips-container (esp. with `credentials:`) is folklore, not documented contract.
- **Option B — release runs host-side in all modes:** drop `container:` from the release/automation set entirely; every mode provisions via the composite (direnv → repo's own flake; container/bare → `nix develop github:vig-os/devkit?ref=<DEVKIT_VERSION>` via Cachix — the `.vig-os` pin still governs the toolchain version). This is how the devkit releases itself. Image parity stays covered by `ci.yml` on the release PR and by the smoke-test repo.

Spike Option A first; if clean, use A for `ci.yml` + release set and collapse the three drifting `ci.yml` overlays into one file. If fragile, adopt B for the release set and keep `ci.yml` on thin overlays around the composite. Outcome recorded as an ADR in `docs/rfcs/`.

### Work breakdown

| Item | Issue | Size |
|------|-------|------|
| Spike conditional `container:` semantics + ADR | new (sub) | S |
| Expose vig-utils console scripts host-side (dev-shell + pinned uv-tool path for bare) | new (sub) | S–M |
| `setup-devkit-toolchain` composite action (scaffolded into consumers) | new (sub) | M |
| Convert `ci.yml` (collapse overlays per spike) + convert release/automation set | #991 | L |
| D1 residual: mode-filter leftover container-only artifacts, truthful preview | #989 | S–M |
| D2: opt-in `--prune-devcontainer` + prompt + preview + MIGRATION.md runbook | #990 | S |
| actionlint adoption (flake + pre-commit + rendered per-mode trees in bats) | new (sub) | S |

Order: spike → vig-utils/actionlint/#990 (parallel) → composite → #991 conversions → #989 → release **1.1.0** → resume rollout (commit-action pilot). Bare-mode release is **in scope** (pinned uv-tool path).

### Smoke-test repo decision

**Keep `devkit-smoke-test` single-mode** (container lane + release-pipeline E2E). Mode coverage lives in the devkit: per-mode rendered-workflow bats assertions + actionlint. The commit-action pilot is the live direnv validation immediately after 1.1.0; bare has no consumer yet and is validated hermetically. #991's "smoke-tested across all three modes" AC is reworded accordingly. A real-runner direnv leg in the smoke-test dispatch is a deferred follow-up, not part of this epic.

### Additional fixes surfaced

- Devkit-own `sync-main-to-dev.yml` is the lone devkit-own workflow still on container+resolve-image (stale template copy) — separate cleanup issue, not blocking.
- Devkit's own `.vig-os` carries no `DEVKIT_MODE`; smoke-test's says `both` while its automation deploys `--docker` — trivial truthfulness fixes folded into the work above.
- Pilot-side notes (not devkit scope): commit-action needs npm-mapped `justfile.project` recipes, node in `extraPackages`, release-app secrets; #990 then prunes its broken apt `.devcontainer/`.

### Execution mechanics

Epic integration branch `feature/988-mode-aware-scaffold` with a draft PR into `dev` (carries automated CI for the integrated state). Sub-issue branches PR into the epic branch (no automated CI there; targeted local CI per PR: bats, pytest scope, prek, actionlint).


---

# [Comment #2]() by [c-vigo]()

_Posted on July 13, 2026 at 09:45 AM_

## Epic implementation complete on the integration branch

All seven sub-issues are merged into `feature/988-mode-aware-scaffold` and closed:

| Sub-issue | PR(s) | Delivered |
|---|---|---|
| #992 spike | #998 | Option A validated on real runners; ADR `docs/rfcs/ADR-conditional-container-toolchain.md` |
| #993 vig-utils | #999 | `prepare-changelog`/`renovate-changelog-pr` in every dev-shell; pinned bare-mode uv-tool path |
| #990 prune | #1000 | Opt-in `--prune-devcontainer` + prompt + preview; #738 default intact |
| #995 actionlint | #1001 | actionlint 1.7.12 in toolchain + devkit hook + per-mode rendered-tree bats fixtures |
| #994 composites | #1002 | `resolve-toolchain` + `setup-devkit-toolchain` scaffolded actions |
| #991 conversion | #1005, #1006 | One mode-aware `ci.yml` (overlays removed); all 8 release/automation workflows on resolve-once threading; scaffold `resolve-image` retired; choreography unchanged |
| #989 D1 residual | #1007 | `container-ci-quirks.md` mode-filtered; truthful preview; devkit `.vig-os` declares `DEVKIT_MODE=direnv` |

Follow-ups filed outside the epic: #1003 (re-enable actionlint shellcheck + harden run-blocks), #996 (devkit-own `sync-main-to-dev.yml` off the container).

**Acceptance criteria:** D1/D2/D3 and single-source choreography are ticked. The
"direnv/bare consumer's CI and release run container-free" AC is implemented and
hermetically verified (per-mode rendered trees + actionlint + 246-test bats
suite); its **live** validation is deliberately deferred to the rollout pilot
(`vig-os/commit-action`, direnv) right after release, per the plan — the
smoke-test repo continues to cover the container lane end-to-end.

**Next steps:** review/merge draft PR #997 (epic → `dev`, full CI runs there),
release **1.1.0**, then resume the rollout with the commit-action pilot
(vig-os/commit-action#29: npm-mapped `justfile.project` recipes, node in
`extraPackages`, release-app secrets, `--prune-devcontainer` for the stale
apt container).

---

# [Comment #3]() by [c-vigo]()

_Posted on July 13, 2026 at 09:51 AM_

## Local validation runbook: mode-aware scaffold via the dev image

Purpose: validate epic #988 end-to-end **locally** against the image actually
shipped to consumers, before merging #997. Parameterized by image tag —
**run now with `dev`** (local `just build` of the epic branch), **repeat with
the RC tag** during the release cycle (pulled from GHCR; that run also drops
the local-path overrides marked ⟨RC⟩ below).

What this adds over the merged bats/pytest suites: bats renders templates from
the **repo checkout** — this runbook exercises the **baked** image assets
(`/root/assets/workspace`, build-time placeholder manifest, `VERSION` record),
the real `install.sh`/`podman run` delivery path, and actual toolchain
execution per mode (not structural greps).

### Phase 0 — Build & image sanity (sequential)
1. `just build` on the epic branch → `ghcr.io/vig-os/devcontainer:dev` (podman).
   ⟨RC⟩ replace with `podman pull ghcr.io/vig-os/devcontainer:<rc-tag>`.
2. Image assertions: vig-utils console scripts on image PATH (#993 — and the
   lowPrio/pythonEnv duplication resolves in pythonEnv's favor);
   `/root/assets/workspace` contains the two composites and the single ci.yml,
   contains NO `.github/actions/resolve-image/` and NO overlay dirs;
   `/root/assets/VERSION` sane.
3. Regression: `uv run pytest tests/test_image.py` against the dev tag (the
   suite devkit CI runs post-build).

### Phase 1 — Scaffold matrix from the image (per-mode, parallel)
For each mode `devcontainer | direnv | both | bare`, scaffold a fresh temp
workspace **through the image** (podman run of the baked `init-workspace.sh`,
plus one `install.sh --version dev` pass to cover the wrapper): assert mode
shape (composites present in every mode; `container-ci-quirks.md` and
`.devcontainer/` only in container-ish modes; `.vig-os` pins version+mode),
`actionlint` clean over the **baked-rendered** `.github/`, `--force --preview`
idempotency, and the #990 container→direnv migration with
`--prune-devcontainer` over a devcontainer-shaped tree.

### Phase 2 — Toolchain execution per mode (the meat, parallel)
Run the real CI contract and the release-tool surface in each mode's actual
environment, mimicking what the converted workflows do:
- **container**: mount the scaffolded workspace into the dev image (podman),
  apply the composite's container branch env (`UV_PROJECT_ENVIRONMENT`,
  `PREK_HOME`, safe.directory), then `just sync && just precommit && just test`;
  verify `retry`, `prepare-changelog`, `renovate-changelog-pr`, `gh`, `jq`,
  `prek`, `uv` resolve.
- **direnv**: `nix develop` on the scaffolded flake with the `vigos` input
  overridden to the local epic checkout (`--override-input vigos path:…`) —
  ⟨RC⟩ drop the override and pin the RC ref instead; same contract + tool set
  (this is the #993 dev-shell delivery validated through a real consumer flake).
- **bare**: composite bare branch in isolation (`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`
  sandboxed): `uv tool install rust-just prek` + vig-utils from
  `git+https://github.com/vig-os/devkit@feature/988-mode-aware-scaffold`
  (the literal URL form the composite uses — ⟨RC⟩ `@<rc-tag>`); same contract +
  tool set.
- All modes: execute the extracted `resolve-toolchain` resolve script against
  the scaffolded `.vig-os` (mode/image/tag outputs incl. the corrupt-mode
  refusal) and source the composite's retry shim + one failing/succeeding
  `retry` invocation.

### Phase 3 — Release-tool dry exercise (folded into Phase 2 agents)
`prepare-changelog prepare|unprepare` roundtrip on a temp copy of the
scaffolded CHANGELOG and `renovate-changelog-pr --help`, in each mode's
environment — the release choreography's tool calls, without touching GitHub.

### Out of scope locally (covered elsewhere)
GitHub-side semantics (empty-image `container:`, workflow_call threading) —
proven by the #992 spike on real runners and re-proven live by the RC cycle's
smoke-test lane + the commit-action pilot.

### Exit criteria
Consolidated pass/fail matrix (mode × {scaffold, actionlint, contract, tools,
release-tools, upgrade/prune}). Any failure → issue on vig-os/devkit, fix on
the epic branch, re-run the affected lane.


---

# [Comment #4]() by [c-vigo]()

_Posted on July 13, 2026 at 10:03 AM_

## Local validation results — dev image (runbook above, first execution)

Image: `ghcr.io/vig-os/devcontainer:dev` (local `just build` of the epic branch @ `0e3ba2e8`). **All lanes green — no defects found.**

| Lane | Coverage | Result |
|---|---|---|
| Phase 0 sanity | Baked assets: composites present, `resolve-image`/overlays absent, vig-utils + `retry` on image PATH | PASS |
| pytest regression | `test_image.py` 116/116; `test_integration.py`+`test_install_script.py` 145/146 (+3 expected skips) — the 1 failure is host-local `gh` multi-account/`dbus-launch`, unrelated surface, passes in CI | PASS |
| container (devcontainer/both) | Scaffold via podman + `install.sh --skip-pull`; shape, placeholders, actionlint, `--force --preview` idempotency, #990 migration (prune `.devcontainer/` + `container-ci-quirks.md`), in-container CI contract (`just sync/precommit` green on feature branch, full tool set resolves), release tools | PASS |
| direnv | Scaffold shape (no `.devcontainer/`, no quirks doc), actionlint, **consumer `mkProjectShell` dev-shell delivers the full tool set incl. `prepare-changelog`/`renovate-changelog-pr` (#993 proven through a real consumer flake)**, `just precommit` green, resolve script (`mode=direnv`, empty image, corrupt-mode refusal), retry shim, release tools | PASS |
| bare | Scaffold shape, actionlint, isolated `uv tool install` incl. the **literal `git+https://…@<ref>#subdirectory=packages/vig-utils` URL end-to-end from GitHub**, pinned versions confirmed, fail-fast on empty `devkit-version`, resolve script (`mode=bare`, empty image), retry shim, release tools, no host pollution | PASS |

Recurring non-defects (documented so the RC run doesn't re-triage them):
`prepare`/`unprepare` are not strict inverses by design; `just sync|test` no-op on the language-neutral scaffold (`pyproject.toml` guard); `no-commit-to-branch` fires on `master` in test harnesses (working as designed); NixOS host needs a glibc loader shim for manylinux prebuilts (native on ubuntu runners).

**Runbook corrections for the RC repetition:**
- `install.sh` has no `--no-prompts` (that's the inner script's flag) — the wrapper is non-interactive when given `--name/--org/--repo`.
- There is **no local-image auto-detection**: use the (currently undocumented) `--skip-pull` flag with a local tag; with a published RC tag, plain `--version <rc-tag>` pulls from GHCR as normal.
- At RC: assert the baked `/root/assets/VERSION` equals the RC tag (on the dev build it shows the flake's `1.0.1` pin and the pin is forwarded via `VIG_OS_VERSION=dev` instead — worked as designed).

Green light from local validation: ready for #997 review → merge → 1.0.x→1.1.0 RC cycle, where this runbook re-runs against the RC image.

---

# [Comment #5]() by [c-vigo]()

_Posted on July 13, 2026 at 10:08 AM_

Additional evidence: a real **container→direnv migration dry-run on the pilot repo** (`commit-action`, throwaway branch, host-side scaffold from the epic checkout with `--mode direnv --prune-devcontainer --force`) passed every epic check — old `.devcontainer/` (incl. the broken post-create.sh, commit-action#30) pruned, quirks doc excluded, composites scaffolded, mode-aware ci.yml actionlint-clean, `.vig-os` persisted, #738 preserves intact, and the scaffolded flake evaluates against the epic devkit. Pilot-side prerequisites unchanged (node in `extraPackages`, npm recipes — commit-action#29). One leftover surfaced outside epic scope: the flake stub still references `github:vig-os/devcontainer` post-rename → filed #1009.

