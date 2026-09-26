---
type: issue
state: closed
created: 2026-09-25T12:47:31Z
updated: 2026-09-25T19:36:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1710
comments: 3
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:41.478Z
---

# [Issue 1710]: [[FEATURE] Opt-in environment binding for the commit-App token-minting jobs in stamped workflows](https://github.com/vig-os/devkit/issues/1710)

### Description

Add a scaffold-level, opt-in way for a consumer repository to bind the jobs that mint the commit App token to a GitHub deployment environment, so the `COMMIT_APP_CLIENT_ID` / `COMMIT_APP_PRIVATE_KEY` pair can live as **environment secrets** behind a deployment branch policy instead of as organization/repository secrets.

Affected stamped workflows (regenerated on upgrade, so a hand-added `environment:` key does not survive — the binding has to come from the stamp itself):

- `sync-issues.yml` — the mirror's commit job
- `prepare-release.yml` — the prepare job (branch cut + changelog freeze)
- `release.yml` / `release-core.yml` — the jobs that mint the commit token (changelog date stamp, optional dist bundle)

`prepare-release-extension.yml` is seeded rather than stamped ("yours to edit"), so a consumer whose extension mints the token adds the binding there itself — worth a documented note, not a stamp change.

### Problem Statement

Today the stamped workflows read the commit App credentials from wherever GitHub resolves the secret names, which in practice is organization or repository secrets — readable by a workflow job on **any branch** of the repository. Since the commit App typically holds a branch-protection bypass (that is what lets the mirror and the changelog freeze push where they push), any account with write access can push a branch whose workflow mints the token and writes straight past the default branch's protection: no PR, no required checks.

A downstream consumer organization wants to close that surface by moving the pair into environment secrets on an environment whose deployment branch policy names the refs these workflows legitimately run from. That only works if the token-minting jobs carry `environment: <name>` — and only devkit can put it there durably.

### Proposed Solution

An opt-in scaffold configuration key (naming/placement up to devkit's config conventions), default **off**:

- unset → workflows render exactly as today; consumers without the environment are unaffected;
- set to an environment name → the stamp renders `environment: <name>` on precisely the token-minting jobs listed above, nothing else.

Creating the environment, its deployment branch policy, and moving the secrets stays the consumer's responsibility; the docs for the option should state the recommended policy: `main` plus `release/*`, since the release workflows are dispatched both from the trunk and from `release/X.Y.Z` branches, and a job bound to an environment can only run from a ref its branch policy admits.

### Alternatives Considered

- **Narrow org-secret visibility to the consuming repos** — shrinks blast radius across the org but leaves every branch *within* those repos able to mint the token. Complementary, not sufficient.
- **Narrow the App installation's repository selection** — same limitation.
- **Hand-editing the stamped workflows downstream** — works until the next devkit upgrade regenerates them; that fragility is the reason for this request.

### Additional Context

Honest limit worth stating in the docs: deployment branch policies match ref **names**, so a write-access account can still create a branch literally named `release/…` and bind the environment from it. The binding is still a strict narrowing (arbitrary feature branches lose the token entirely), and consumers who need more can pair it with a ruleset restricting who may create `release/*` refs.

### Impact

- Opt-in and default-off: fully backward compatible; no consumer changes behavior until it sets the key.
- Consumers that enable it must create the environment **before** upgrading, otherwise the first bound run auto-creates an unprotected environment.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 05:00 PM_

## Triage 2026-09-25: implement, with three corrections to the request

**Mechanism.** Consumer workflows are managed files (rsync of `assets/workspace/`, not in `PRESERVE_FILES`); knobs are realised by post-copy anchored `sed` render functions (`render_workflow_model`, `render_sync_settings`, `render_actionlint_optout`, `render_commit_types`, …) reading `.vig-os` via `read_manifest_value` and writing the key back so upgrades keep it. That is the pattern to follow: a `DEVKIT_COMMIT_APP_ENVIRONMENT=` key (bare in the template `.vig-os`), validated against GitHub's environment-name charset, and a `render_commit_app_environment()` that appends `    environment: <name>` under each token-minting job key when set. `DEVKIT_CI_RUNNER`'s runtime `fromJSON` trick does not apply (`environment` cannot read `.vig-os` at run time), and an always-rendered `environment: ${{ vars.X }}` cannot be default-off (an empty name is invalid), so literal insertion it is.

**Correction 1 — the job list is 8, not 3.** Every stamped job that mints the commit App token (`grep COMMIT_APP assets/workspace/.github/workflows/`):

| Workflow | Job | Ref it runs from |
|---|---|---|
| `sync-issues.yml` | `sync` (mints twice) | default branch (schedule / dispatch) |
| `prepare-release.yml` | `prepare` | `dev` (gitflow default `--ref dev`) |
| `prepare-release.yml` | `rollback` | same run |
| `prepare-hotfix.yml` | `prepare` | `dev` |
| `prepare-hotfix.yml` | `rollback` | same run |
| `release.yml` | `rollback` | `release/X.Y.Z` |
| `release-core.yml` | `finalize` (`workflow_call` callee) | caller's ref: `release/X.Y.Z` |
| `sync-main-to-dev.yml` | `sync` (gitflow only) | `main` |

`prepare-release-extension.yml` is preserved and its template mints nothing → docs note only, as the issue says. No token-minting job runs on `pull_request`, so the merge-ref limitation is not a blocker.

**Correction 2 — the branch policy must admit `dev` under gitflow**, not only `main` + `release/*`: `prepare-release` / `prepare-hotfix` dispatch from `dev` by default. A policy without `dev` breaks the first cut.

**Correction 3 — the reusable callee.** `on.workflow_call` does not support `environment`, and the `github` context in a reusable workflow is the caller's, so the key goes on `release-core.yml`'s `finalize`, not on `release.yml`'s `core:` (`uses:`) job. With the pair living only as environment secrets, `secrets: inherit` cannot resolve them at the caller, so `release-core.yml`'s `COMMIT_APP_CLIENT_ID` / `COMMIT_APP_PRIVATE_KEY` must become `required: false` when the knob is set, the callee's job-level environment supplying them. GitHub documents that a job-level `environment` in the reusable workflow makes the environment secret win over the passed one — but this is the one behaviour that wants a **live proof** before a train relies on it.

Also confirmed: a bound job on a missing environment auto-creates an unprotected one, so "create it first" belongs in the docs, with "no required reviewers" (a reviewer gate would inject a second approval into the single-approval train).

**Plan:** knob read/validate/writeback; `render_commit_app_environment()` behind `[[ -f ]]` guards (feature prunes, trunk skips `sync-main-to-dev.yml`); `required: false` flip in `release-core.yml` when set; tests — unset ⇒ rendered tree byte-identical to the templates, set ⇒ `environment:` on exactly these 8 jobs and no other in the whole tree, trunk variant, bad name refused, `.vig-os` round-trip, actionlint over the rendered tree; docs in `MIGRATION.md` (knob table + subsection), `WORKFLOW_SECURITY.md` (threat model), `RELEASE_CYCLE.md` secrets note, the extension note and the create-first caveat. Effort ≈ 1–1.5 days; **semver: minor**.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 06:47 PM_

Implemented in #1724 (branch `feature/1710-commit-app-environment`), **not merged**: the PR body carries the live-proof checklist for `devkit-smoke-test` (environment `commit-app`, policy `main` + `release/*` + `dev` under gitflow, no reviewers, secrets moved and org/repo copies removed, then `prepare-release.yml` from `dev` and `release.yml` candidate from `release/X.Y.Z`; watch the callee's `Generate commit app token` step). Scope as triaged plus a 9th job the template grep cannot see — `promote-release.yml:reset-sync-mirror`, injected in mirror mode — bound because leaving it out would break promote the moment a consumer moves the pair. The rendered scalar is single-quoted so a name like `true` or `0755` stays a string.

---

# [Comment #3]() by [c-vigo]()

_Posted on September 25, 2026 at 07:36 PM_

Shipped in #1724, merged to `dev` (6fa8c6b4). Opt-in `DEVKIT_COMMIT_APP_ENVIRONMENT`; nine token-minting jobs bound (the eight stamped ones plus the mirror-mode reset job); `release-core.yml`'s `COMMIT_APP_*` flipped to `required: false` when set. The reusable-callee mechanism is live-proven on devkit-smoke-test (see the PR): the callee's job-level environment supplies the pair under `secrets: inherit`, the environment value wins over the same-named org secret, and an out-of-policy branch is refused. Consumers receive the knob with the next release; setup order and the branch policy (`main` + `release/*`, plus `dev` under gitflow) are in `docs/MIGRATION.md`.

