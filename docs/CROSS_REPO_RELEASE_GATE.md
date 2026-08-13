# Cross-Repo Release Validation Gate

This document describes the dedicated cross-repository validation gate used by the release pipeline.

## Rationale

The release pipeline publishes candidate and final tags in the main repository. A separate validation repository executes post-publish verification against those tags.

This gate exists to:

- validate release artifacts outside the release repository execution context
- enforce a consistent candidate-to-final promotion rule
- provide an auditable, machine-checkable signal before finalization
- keep release orchestration and validation responsibilities separated

## How It Works

### Triggering

During release publish, the orchestrator sends a `repository_dispatch` event to `vig-os/devkit-smoke-test`.

Payload contract:

- Required:
  - `client_payload[tag]`
- Required for current gate behavior:
  - `client_payload[release_kind]` (`candidate` or `final`)
- Optional source context:
  - `client_payload[event_type]`
  - `client_payload[source_repo]`
  - `client_payload[source_workflow]`
  - `client_payload[source_run_id]`
  - `client_payload[source_run_url]`
  - `client_payload[source_sha]`
  - `client_payload[correlation_id]`

Workflow dispatch contract:

- Required downstream workflow IDs/files:
  - `prepare-release.yml`
  - `release.yml`
  - `promote-release.yml`
- Required dispatch ref:
  - `dev`
- Dispatch and wait operations must use the same ref context to avoid default-branch drift:
  - dispatch via `gh workflow run <workflow> --ref dev ...`
  - run discovery via `gh run list --workflow <workflow> --branch dev --event workflow_dispatch ...`
- Every wait binds to the run its own job dispatched ([#1477](https://github.com/vig-os/devkit/issues/1477)). The receiver stamps a `DISPATCH_TS` immediately before `gh workflow run` (backdated 60 s against runner/server clock skew) and accepts only a run whose `createdAt` is at or after that stamp **and** whose `databaseId` exceeds the baseline captured with the *same* `--workflow`/`--branch`/`--event` filters. The first matching run is locked on for the rest of the wait — a later run cannot hijack it — and its id and URL are logged. With no bound run the wait polls to its timeout and fails loudly; it never reports the conclusion of a run it did not dispatch. An id-ordering guard alone matched the previous RC's completed run on the 1.8.0 final, and promote was dispatched before the release existed.

### Receiver Responsibilities

The receiver workflow (`assets/smoke-test/.github/workflows/repository-dispatch.yml`) performs:

1. payload validation and metadata normalization
2. deploy orchestration in the validation repository
3. release artifact publication for the dispatched tag:
   - candidate tag -> GitHub pre-release
   - final tag -> GitHub release (draft until promoted)
4. idempotency checks when a release object already exists
5. preflight validation that required downstream workflow IDs are resolvable on the dispatch ref before orchestration starts
6. release PR approval gate (`Gate final release on human approval of release PR`), before the downstream `release.yml` is triggered:
   - **candidate:** the freshly created release PR is intentionally left **unapproved** — approval gates the final release only (deferred-approval model, [#902](https://github.com/vig-os/devkit/issues/902)), so the candidate chain runs green end-to-end with no human step
   - **final:** the gate polls the PR's `reviewDecision` (20 s interval, up to 30 min) until a **human** approves the freshly created release PR; workflow-token self-approval is blocked org-wide and cannot be used (see [Contract dependencies](#contract-dependencies))
   - on timeout the gate fails the run; **recovery:** approve the release PR, then re-run the failed jobs of the same listener run to resume the final release
7. after downstream `release.yml` completes: wait until required checks on the release PR are green (candidate and final)
8. **final only:** dispatch downstream `promote-release.yml` on `dev` with `version` set to the base semver so the draft GitHub Release is published, the release PR is merged to `main`, and RC git tags are cleaned up (see workspace `promote-release.yml`). **Candidate:** the release PR stays open after checks pass; it is not merged by the receiver.

Every dispatch (each RC and the final) recreates the release branch and PR from scratch (cleanup-recreate semantics), so an up-front approval cannot survive to the final dispatch — the human approval necessarily happens **while the final dispatch is paused at the gate**. Operator step: [RELEASE_CYCLE.md, Phase 5](RELEASE_CYCLE.md#phase-5-post-release-cleanup).

If the validation repository also runs the shipped workspace `release.yml` workflow for a **candidate** (separate from publishing a release for the dispatched tag), pass workflow input `rc-number` set to the numeric RC suffix of `client_payload.tag` (for example `21` for `0.3.1-rc21`). That keeps the downstream candidate tag aligned with the upstream publish tag. The smoke-test template exposes this value as job output `needs.validate.outputs.rc_number`.

### Gate enforcement

**`vig-os/devcontainer` `release.yml`:** Dispatches downstream validation during publish but does **not** block on downstream GitHub Release state for RC or final tags. The former validate step that required a published downstream pre-release for the latest RC before finalization was **removed**; it duplicated concerns now owned by promotion.

**`vig-os/devcontainer` `promote-release.yml`:** Before updating GHCR `:latest`, publishing the draft GitHub Release, and merging the release PR, the `validate` job requires a **published** downstream release for the final version tag on `vig-os/devkit-smoke-test` that is **not** a draft and **not** a pre-release (`Verify downstream published final release`). For the canonical smoke-test flow, the receiver dispatches downstream `promote-release.yml` after `release.yml` and required release PR checks succeed, which publishes the downstream final release so this gate is satisfied without a manual publish step on the smoke-test repo.

If promote validation fails, retry after the downstream release is in the expected state; `release.yml` rollback handling applies only to failures within that workflow.

### Contract dependencies

The approval gate has two external dependencies that are part of this contract. Both were discovered the hard way on the 1.7.0 train ([#1391](https://github.com/vig-os/devkit/issues/1391)):

1. **Smoke-test `main` must require at least one approving review.** The gate polls `reviewDecision`, which GitHub only computes when the PR's base branch *requires* reviews — with a review count of 0, a human approval never surfaces as `reviewDecision=APPROVED` and the gate times out. The setting is owned by `vig-os/org-config` (`devkit-smoke-test` → `Main protection` → `required_approving_review_count: 1`, applied by [org-config#127](https://github.com/vig-os/org-config/issues/127) and guarded by an inline comment in `vig-os.jsonnet`). Workflow-token approvals are blocked org-wide ([org-config#122](https://github.com/vig-os/org-config/pull/122), `actions_can_approve_pull_request_reviews: false`, not overridable per-repo), so the required review is necessarily human.
2. **The listener executes from the smoke-test repo's default branch (`main`).** `repository_dispatch` always runs the workflow version on the default branch — changes to `repository-dispatch.yml` that have only reached smoke-test `dev` are **not** live. The devkit asset (`assets/smoke-test/.github/workflows/repository-dispatch.yml`) is the source of truth; it reaches smoke-test `main` through the smoke repo's own release cycle. For urgent listener fixes, hotfix smoke-test `main` directly **and** mirror the change in the devkit asset so the next scaffold deploy converges rather than reverts (precedents: [devkit-smoke-test#345](https://github.com/vig-os/devkit-smoke-test/pull/345), [#353](https://github.com/vig-os/devkit-smoke-test/pull/353)).

**Immutable releases:** Where **immutable releases** are enabled, a **published** GitHub Release (including a published **pre-release**) locks its **linked** tag and assets; they cannot be rewritten via normal GitHub UI/API. Downstream and smoke-test flows should fix forward with a new RC or version rather than deleting tags or releases. See [Immutable releases, tag rulesets, and forward-fix policy](RELEASE_CYCLE.md#immutable-releases-tag-rulesets-and-forward-fix-policy) for full policy and recovery procedures (including tags without a published release and the forward-fix no-delete policy).

## Expected Output

### Success Signals

Expected release-run logs include messages equivalent to:

```
✓ Triggered validation dispatch for release tag: X.Y.Z-rcN
✓ Downstream release completed successfully for X.Y.Z-rcN
```

or for final:

```
✓ Triggered validation dispatch for release tag: X.Y.Z
✓ Downstream release completed successfully for X.Y.Z
```

### Expected Downstream Release State

- For candidate publish:
  - tag exists in downstream repo as a pre-release
- For final publish:
  - tag exists in downstream repo as a non-pre-release release

### Failure Signals

Common failure patterns:

- no downstream release found for expected tag within timeout
- downstream release type mismatch (`prerelease` flag differs from expected)
- malformed/insufficient dispatch payload
- downstream workflow failure prior to release artifact publication
- workflow contract drift (required workflow ID missing on expected dispatch ref), which must fail fast in preflight
- **final only:** `Timed out waiting for human approval of release PR` — either nobody approved the smoke release PR within the 30-minute gate window, or the approval never computed as `reviewDecision=APPROVED` because required reviews on smoke-test `main` were dropped (see [Contract dependencies](#contract-dependencies)). Recovery for the former: approve the PR, then re-run the failed jobs of the listener run. The latter is config drift and must be fixed in `vig-os/org-config` first.

## Operational Verification

Examples for manual inspection:

```bash
gh -R vig-os/devkit-smoke-test run list --workflow repository-dispatch.yml --limit 5
gh -R vig-os/devkit-smoke-test run view <RUN_ID>
gh -R vig-os/devkit-smoke-test release view <TAG>
```

## Source of Truth

- Publish and dispatch: `.github/workflows/release.yml`
- Promote-time downstream release gate: `.github/workflows/promote-release.yml`
- Validation receiver template: `assets/smoke-test/.github/workflows/repository-dispatch.yml`

## Token Model for Downstream Write Paths

For downstream workflow templates used by this gate, repositories must provide both Commit and Release app credentials.

- Commit App token is required for protected branch writes performed by release preparation/finalization flows.
- Release App token is required for PR/release/workflow dispatch orchestration.

Using `github.token` for protected downstream write paths is not supported by this gate contract because branch rulesets may reject direct writes without app bypass.
