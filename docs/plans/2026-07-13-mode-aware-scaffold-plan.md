# Plan: Mode-aware scaffold — CI/release toolchain per deployment mode

**Issue**: #988 (sub-issues #989–#995)
**Date**: 2026-07-13
**Design decision**: One release choreography + shared `setup-devkit-toolchain`
composite branching on `DEVKIT_MODE`; job-level container selection decided by
the #992 spike (Option A conditional `container:` vs Option B host-always release).

---

## Scope corrections from research

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
