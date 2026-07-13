---
rfc: ADR-conditional-container-toolchain
date: 2026-07-13
title: Mode-aware toolchain selection — conditional job-level container: (Option A)
status: accepted
authors:
- Carlos Vigo (c-vigo)
---

# ADR: Conditional job-level `container:` for mode-aware toolchain selection

**Decision (TL;DR):** Adopt **Option A**. A first `resolve-toolchain` job outputs
an `image` string — empty in the `direnv`/`bare` (host) modes, the devcontainer
image in `container` mode — and every downstream job declares
`container: image: ${{ needs.resolve-toolchain.outputs.image }}`. A **spike on
real GitHub-hosted runners (#992) proved that an empty image expression makes the
job run directly on the host runner, with no error, and that a `credentials:`
block present alongside an empty image is silently ignored rather than fatal.**
The behaviour holds unchanged across a `workflow_call` boundary (image threaded
via `inputs`). Container mode stays byte-identical to today. Option B
(drop `container:` everywhere, provision via the composite in all modes) is
recorded as the fallback but is **not** adopted, because A gives us a single
source of truth for image selection and zero behavioural change in container mode.

## Problem statement

Epic #988 makes the devkit's CI/release workflows mode-aware: the same scaffolded
workflow must run its steps inside the devcontainer image (`container` mode — the
status quo) **or** directly on the host runner and provision the toolchain via
Nix/`uv` (`direnv` and `bare` modes). A shared `setup-devkit-toolchain` composite
action (#994) branches on `DEVKIT_MODE` and, via the `GITHUB_PATH`-export pattern,
makes plain `run:` steps work in every mode — but a **composite action cannot set
a job-level `container:`**. That decision has to be made at the workflow level,
and job-level `container:` cannot be conditionally *unset* by a documented
`if:`-style contract. The plan (`docs/plans/2026-07-13-mode-aware-scaffold-plan.md`)
framed two resolutions and gated #991 (workflow conversion) and #994 (composite)
on validating the first:

- **Option A — conditional container.** A `resolve-toolchain` job outputs `mode`
  and `image` (empty unless container mode); every job declares
  `container: image: ${{ needs.resolve-toolchain.outputs.image }}`. Single-source,
  container-mode byte-identical to today. **Risk:** "empty image ⇒ runs on host"
  (especially with a `credentials:` block present) was folklore, not a documented
  contract — if it errored, the pattern was unusable.
- **Option B — host-side release in all modes.** Drop `container:` from the
  release/automation set entirely and provision via the composite in every mode
  (`nix develop github:vig-os/devkit?ref=<DEVKIT_VERSION>` for container/bare, the
  repo flake for direnv). This is how the devkit releases itself; image parity
  stays covered by `ci.yml` on the release PR and the smoke-test repo.

This ADR records the spike that settled the question.

## The spike

A temporary workflow pair (`.github/workflows/spike-992-conditional-container.yml`
- a reusable `spike-992-reusable.yml`), triggered `on: pull_request` with no
branch filter, ran on **GitHub-hosted `ubuntu-24.04` runners** via PR
[vig-os/devkit#998](https://github.com/vig-os/devkit/pull/998) into the epic
branch. A `resolve` job emitted two outputs — `empty` (`""`) and
`image` (`ubuntu:24.04`) — and each case job printed `hostname`, `id -u`, `$HOME`
and `/etc/os-release` as evidence. The workflow files are **temporary and were
removed from the branch after the spike**; the run logs persist as the evidence.

**Evidence — run
[29231840324](https://github.com/vig-os/devkit/actions/runs/29231840324)
(all seven jobs succeeded):**

| # | Case | `container:` input | `hostname` | `id -u` | `$HOME` | Result |
|---|------|--------------------|------------|---------|---------|--------|
| 1 | empty image, no credentials | `image: ${{ …empty }}` | `runnervm5mmn9` (host VM) | `1001` | `/home/runner` | **Runs on host, no error** |
| 2 | empty image **with** `credentials:` (`github.actor`/`github.token`) | `image: ${{ …empty }}` + creds | `runnervm5mmn9` (host VM) | `1001` | `/home/runner` | **Runs on host; credentials block silently ignored, no error** |
| 3 | non-empty image | `image: ubuntu:24.04` | `abc73f6ef113` (container) | `0` (root) | `/github/home` | **Runs in container** (`docker create … ubuntu:24.04`) |
| 4a | reusable `workflow_call`, empty image | `inputs.image = ""` | `runnervm5mmn9` (host VM) | `1001` | `/home/runner` | **Runs on host across the `workflow_call` boundary** |
| 4b | reusable `workflow_call`, non-empty image | `inputs.image = ubuntu:24.04` | `617022bc2953` (container) | `0` (root) | `/github/home` | **Runs in container across the boundary** |
| 5 | whole `container:` map as an expression → `null` when empty | `container: ${{ …empty != '' && fromJSON(format('{{"image":"{0}"}}', …empty)) || null }}` | `runnervm5mmn9` (host VM) | `1001` | `/home/runner` | **Runs on host; the map-or-`null` expression form also works** |

Key observations:

- The host cases show the standard hosted-runner signature — non-root
  `id -u = 1001`, `$HOME = /home/runner`, a `runnervm…` hostname, and **no
  `Initialize containers` / `docker create` step** in the job log. The container
  cases show `id -u = 0`, `$HOME = /github/home`, a container-ID hostname, and an
  explicit `docker create … ubuntu:24.04 …` step.
- **Case 2 is the decisive one for the folklore risk:** a `credentials:` block
  (username `${{ github.actor }}`, password `${{ github.token }}`) present while
  the image expression is empty does **not** trigger a login attempt or a schema
  error — the job simply runs on the host, identically to Case 1. So the
  scaffolded workflow can carry the GHCR `credentials:` block unconditionally and
  it is inert in host modes.
- **Case 4a/4b prove output fan-in survives `workflow_call`:** threading the
  resolved image through a reusable workflow's `inputs.image` selects host vs
  container exactly as the top-level pattern does. This matters because the
  release/automation set uses reusable workflows.
- **Case 5** is a bonus: even the more aggressive "make the entire `container:`
  value an expression that yields a map or `null`" form works and lands on the
  host. We do **not** need it — the plain `container: image: <empty>` form
  (Cases 1/2) is simpler and sufficient — but it is a documented fallback if a
  future case ever needs to vary keys beyond `image` conditionally.

## Decision

Adopt **Option A** for both `ci.yml` and the release/automation workflow set:

- A leading `resolve-toolchain` job reads `.vig-os` and outputs `mode` + `image`
  (empty for `direnv`/`bare`, the devcontainer image for `container`).
- Downstream jobs declare `container: image: ${{ needs.resolve-toolchain.outputs.image }}`
  and may carry the GHCR `credentials:` block unconditionally (inert when the
  image is empty).
- Reusable (`workflow_call`) workflows receive the image via an `inputs.image`
  string and apply the same `container: image: ${{ inputs.image }}` pattern.
- The three drifting `ci.yml` per-mode overlays can be collapsed into a single
  file gated on the resolved output, as the plan anticipated for the
  "Option A clean" branch.

Option B is **rejected** for now: A is single-source, leaves container mode
byte-identical to today, and avoids re-plumbing ~2 000 lines of release
choreography to run host-side. B remains the documented fallback should a future
runner/`runner`-image change break the empty-image contract; the smoke-test repo
and `ci.yml`-on-release-PR keep image parity covered regardless.

## Consequences

- **#994 (`setup-devkit-toolchain` composite):** the composite handles
  *provisioning* only (Nix/`uv` + `GITHUB_PATH` export). *Image selection* is a
  workflow-level `resolve-toolchain` job that runs before it — the composite does
  not, and cannot, touch `container:`. Design the composite to be a no-op-friendly
  first step of every job so container-mode jobs (where the toolchain is already
  baked into the image) and host-mode jobs share one call site.
- **#991 (workflow conversion):** convert to the `resolve-toolchain` + `needs`
  pattern; keep the GHCR `credentials:` block in scaffolded jobs unconditionally
  (proven inert when the image is empty). Thread the resolved image through
  `inputs.image` for every `workflow_call` in the release set. The
  container-mode-specific env (`PREK_HOME`, `UV_PROJECT_ENVIRONMENT=/root/…`,
  `safe.directory`) must itself become mode-aware, since those paths only exist in
  the image — but that is orthogonal to the `container:` selection settled here.
- **Caveat — empty-string vs unset:** the contract validated is "empty *string*
  image ⇒ host". The `resolve-toolchain` job must emit an **empty string**
  (`image=`), never omit the output; `needs.*.outputs.*` of an undefined output is
  also empty, but scaffolding should set it explicitly for clarity and to keep
  actionlint/readers honest.
- **Caveat — undocumented contract:** GitHub does not *document* "empty image runs
  on host". It is stable in practice (and now evidenced), but a runner-image change
  could regress it. Mitigation: the per-mode rendered-workflow bats assertions and
  actionlint (planned sub-issues) plus the smoke-test lane will catch a
  regression; Option B stays on file as the escape hatch.
- **No branch-protection dependency:** the pattern is pure workflow YAML and needs
  no repo settings, consistent with the org being on GitHub Free.

## References

- Epic #988; plan `docs/plans/2026-07-13-mode-aware-scaffold-plan.md`.
- Spike issue #992; spike PR
  [vig-os/devkit#998](https://github.com/vig-os/devkit/pull/998).
- Evidence run
  [29231840324](https://github.com/vig-os/devkit/actions/runs/29231840324).
- Gated by this decision: #991 (workflow conversion), #994
  (`setup-devkit-toolchain` composite).
