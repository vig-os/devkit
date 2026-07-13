---
type: issue
state: closed
created: 2026-07-13T07:12:04Z
updated: 2026-07-13T07:29:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/992
comments: 2
labels: chore, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:54.333Z
---

# [Issue 992]: [[SPIKE] Conditional job-level container: — validate empty-image semantics, decide Option A vs B](https://github.com/vig-os/devkit/issues/992)

### Description

Decide the mode-branching mechanism for the workflow refactor (#991): job-level
`container:` cannot be conditionally unset by a documented expression contract.
Validate **Option A** — a `resolve-toolchain` job outputs `image` (empty for
direnv/bare) and jobs declare `container: image: ${{ needs.resolve-toolchain.outputs.image }}`
— on real GitHub runners:

- empty `image` expression → job runs directly on the host runner (no error)
- behavior of the `credentials:` block when `image` is empty
- output fan-in via `needs` across reusable (`workflow_call`) boundaries

Fallback is **Option B**: release/automation workflows drop `container:`
entirely and provision via the composite in all modes
(`nix develop github:vig-os/devkit?ref=<DEVKIT_VERSION>` for container/bare,
repo flake for direnv) — the pattern the devkit itself releases with.

### Method

Temporary spike workflow (`on: pull_request`, no branch filter so it runs on a
PR into the epic branch) exercising: empty-image host job, empty-image +
credentials, non-empty image container job. Deleted after the spike.

### Acceptance Criteria

- [ ] Spike workflow run demonstrates each case with links to run logs
- [ ] ADR in `docs/rfcs/` recording the decision (A or B) and evidence
- [ ] Findings posted on #988

### Related Issues

Gates #991 and the setup-devkit-toolchain composite. Part of #988.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 07:26 AM_

## Spike verdict: **Option A is viable — adopt it**

Validated on real GitHub-hosted `ubuntu-24.04` runners via the temporary spike
workflow in PR #998. Evidence run:
https://github.com/vig-os/devkit/actions/runs/29231840324 (all 7 jobs green).

| # | Case | hostname | `id -u` | `$HOME` | Result |
|---|------|----------|---------|---------|--------|
| 1 | empty image, no creds | host VM | 1001 | `/home/runner` | runs on **host**, no error |
| 2 | empty image **+ `credentials:`** (`github.actor`/`github.token`) | host VM | 1001 | `/home/runner` | runs on **host**; credentials block **silently ignored**, no error |
| 3 | non-empty image (`ubuntu:24.04`) | container id | 0 | `/github/home` | runs in **container** (`docker create …`) |
| 4a | reusable `workflow_call`, empty image | host VM | 1001 | `/home/runner` | **host** across the `workflow_call` boundary |
| 4b | reusable `workflow_call`, non-empty image | container id | 0 | `/github/home` | **container** across the boundary |
| 5 | whole `container:` map as expression → `null` when empty | host VM | 1001 | `/home/runner` | **host**; the map-or-`null` fallback form also works |

**Answers to the spike questions:**

- **Empty `image` expression → host, no error.** (Case 1) The host cases show no
  `Initialize containers`/`docker create` step at all.
- **`credentials:` present while image is empty → ignored, not fatal.** (Case 2)
  Identical host behaviour to Case 1 — so scaffolded jobs may carry the GHCR
  `credentials:` block unconditionally; it is inert in host modes.
- **Output fan-in survives `workflow_call`.** (Cases 4a/4b) Threading the resolved
  image through `inputs.image` selects host vs container exactly as at top level.
- **Bonus fallback:** `container: ${{ x != '' && fromJSON(format('{{"image":"{0}"}}', x)) || null }}`
  also lands on the host (Case 5). Not needed — plain `container: image: <empty>`
  is simpler — but documented as an escape hatch.

**Decision:** Option A — a leading `resolve-toolchain` job outputs `image`
(empty for `direnv`/`bare`, the devcontainer image for `container`); downstream
jobs use `container: image: ${{ needs.resolve-toolchain.outputs.image }}` and
keep the `credentials:` block unconditionally. Container mode stays
byte-identical to today. Option B (host-always release) recorded as the fallback,
not adopted.

**ADR:** `docs/rfcs/ADR-conditional-container-toolchain.md` (in PR #998).

**Caveats for downstream work:**
- **#994 composite:** handles provisioning only (Nix/`uv` + `GITHUB_PATH`
  export); image selection is the workflow-level `resolve-toolchain` job — the
  composite cannot touch `container:`.
- **#991 conversion:** emit `image` as an **empty string** (never omit the
  output); keep GHCR `credentials:` unconditionally; thread the image via
  `inputs.image` for every reusable workflow. The container-only env
  (`PREK_HOME`, `UV_PROJECT_ENVIRONMENT=/root/…`, `safe.directory`) must itself
  become mode-aware — orthogonal to `container:` selection.
- "Empty image ⇒ host" is stable-in-practice but **not GitHub-documented**;
  rendered-workflow bats assertions + actionlint + the smoke-test lane guard a
  regression, with Option B on file as the escape hatch.

Spike workflow files were **removed** from the branch (final commit) so they do
not merge; the run logs above are the persistent evidence.

Refs: #992

---

# [Comment #2]() by [c-vigo]()

_Posted on July 13, 2026 at 07:29 AM_

Spike complete — Option A adopted, ADR merged into the epic branch (feature/988-mode-aware-scaffold) via #998. Evidence: https://github.com/vig-os/devkit/actions/runs/29231840324

