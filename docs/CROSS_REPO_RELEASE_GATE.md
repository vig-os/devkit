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
6. after downstream `release.yml` completes: wait until required checks on the release PR are green (candidate and final)
7. **final only:** dispatch downstream `promote-release.yml` on `dev` with `version` set to the base semver so the draft GitHub Release is published, the release PR is merged to `main`, and RC git tags are cleaned up (see workspace `promote-release.yml`). **Candidate:** the release PR stays open after checks pass; it is not merged by the receiver.

There is deliberately **no human-approval gate** in the receiver ([#1506](https://github.com/vig-os/devkit/issues/1506)): the smoke release PR is entirely bot-authored scaffold output, so an approval of it carried no information. The operative controls are green smoke CI and the published smoke release that devkit's promote gate validates ([Gate enforcement](#gate-enforcement)). The former gate (`Gate final release on human approval of release PR`, [#1391](https://github.com/vig-os/devkit/issues/1391)) was a workaround for review-requiring branch protection, removed together with that requirement (see [Contract dependencies](#contract-dependencies)).

**Deploy PRs are reclaimed by head branch, not by label** ([#1499](https://github.com/vig-os/devkit/issues/1499)). `Close stale deploy PRs` selects every open PR on a `chore/deploy-*` branch as well as any carrying the `deploy` label; the deploy step adopts an open PR already on the deploy branch instead of failing on it, records `pr_url` before anything else can fail, and labels in a separate, retrying, non-fatal step. The branch name is deterministic and is pushed *before* the PR exists, whereas the label is a second mutation that can fail on its own — which is exactly what happened on the 1.9.0 rc1 train, leaving an unlabelled deploy PR that the cleanup could not see. Recovery for a partial create is therefore the ordinary one: re-run the failed jobs.

If the validation repository also runs the shipped workspace `release.yml` workflow for a **candidate** (separate from publishing a release for the dispatched tag), pass workflow input `rc-number` set to the numeric RC suffix of `client_payload.tag` (for example `21` for `0.3.1-rc21`). That keeps the downstream candidate tag aligned with the upstream publish tag. The smoke-test template exposes this value as job output `needs.validate.outputs.rc_number`.

### Gate enforcement

**`vig-os/devcontainer` `release.yml`:** Dispatches downstream validation during publish but does **not** block on downstream GitHub Release state for RC or final tags. The former validate step that required a published downstream pre-release for the latest RC before finalization was **removed**; it duplicated concerns now owned by promotion.

**`vig-os/devcontainer` `promote-release.yml`:** Before updating GHCR `:latest`, publishing the draft GitHub Release, and merging the release PR, the `validate` job requires a **published** downstream release for the final version tag on `vig-os/devkit-smoke-test` that is **not** a draft and **not** a pre-release (`Verify downstream published final release`). For the canonical smoke-test flow, the receiver dispatches downstream `promote-release.yml` after `release.yml` and required release PR checks succeed, which publishes the downstream final release so this gate is satisfied without a manual publish step on the smoke-test repo.

If promote validation fails, retry after the downstream release is in the expected state; `release.yml` rollback handling applies only to failures within that workflow.

### Contract dependencies

The contract has two external dependencies:

1. **Smoke-test `main` must require zero approving reviews, matched to a listener with no approval gate.** Since [#1506](https://github.com/vig-os/devkit/issues/1506) the `Main protection` ruleset sets `required_approving_review_count: 0` ([org-config#167](https://github.com/vig-os/org-config/issues/167)), and the listener carries no approval poll. These two must move **together** — the removal only landed safely because both changes preceded the next train, and either one alone breaks the final leg: the old listener under a count-0 ruleset polls `reviewDecision`, which GitHub only computes when the base branch requires reviews, so even a manual approval never surfaces and the gate times out un-unblockably; the new listener under a count-1 ruleset produces a smoke release PR that cannot merge, because workflow-token approvals are blocked org-wide ([org-config#122](https://github.com/vig-os/org-config/pull/122), `actions_can_approve_pull_request_reviews: false`, not overridable per-repo) and no human is in the loop. Any future change to either side must land the counterpart first, on smoke-test **`main`** (see dependency 2), before the next release train.
2. **The listener executes from the smoke-test repo's default branch (`main`).** `repository_dispatch` always runs the workflow version on the default branch — changes to `repository-dispatch.yml` that have only reached smoke-test `dev` are **not** live. The devkit asset (`assets/smoke-test/.github/workflows/repository-dispatch.yml`) is the source of truth; it reaches smoke-test `main` through the smoke repo's own release cycle. For urgent listener fixes, hotfix smoke-test `main` directly **and** mirror the change in the devkit asset so the next scaffold deploy converges rather than reverts (precedents: [devkit-smoke-test#345](https://github.com/vig-os/devkit-smoke-test/pull/345), [#353](https://github.com/vig-os/devkit-smoke-test/pull/353)). The [#1506](https://github.com/vig-os/devkit/issues/1506) gate removal itself was delivered this way: an explicit PR to smoke-test `main`, not just the template merge.

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
- `pull request update failed` in the deploy job — note *update*, not *create*: the PR was created and the follow-up labelling mutation is what failed. Since [#1499](https://github.com/vig-os/devkit/issues/1499) this is self-healing (the url is recorded first, labelling cannot fail the job, and the cleanup reclaims by branch), so re-run the failed jobs. On a listener version predating that fix — the live listener runs from smoke-test's default branch, see [Contract dependencies](#contract-dependencies) — add the `deploy` label to the open PR by hand *before* re-running, or the re-run deadlocks on "a pull request already exists"
- **final only:** the smoke release PR cannot merge for lack of an approving review — config drift: `required_approving_review_count` on smoke-test `main` was raised above 0 without reinstating a human approval step (see [Contract dependencies](#contract-dependencies), dependency 1). Fix the ruleset in `vig-os/org-config` first, then re-run the failed jobs.

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
