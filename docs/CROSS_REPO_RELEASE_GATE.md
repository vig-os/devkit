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

During release publish, the orchestrator sends a `repository_dispatch` event to `vig-os/devcontainer-smoke-test`.

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
- Required dispatch ref:
  - `dev`
- Dispatch and wait operations must use the same ref context to avoid default-branch drift:
  - dispatch via `gh workflow run <workflow> --ref dev ...`
  - run discovery via `gh run list --workflow <workflow> --branch dev ...`

### Receiver Responsibilities

The receiver workflow (`assets/smoke-test/.github/workflows/repository-dispatch.yml`) performs:

1. payload validation and metadata normalization
2. deploy orchestration in the validation repository
3. release artifact publication for the dispatched tag:
   - candidate tag -> GitHub pre-release
   - final tag -> GitHub release
4. idempotency checks when a release object already exists
5. preflight validation that required downstream workflow IDs are resolvable on the dispatch ref before orchestration starts

### Gate Checks in the Orchestrator

The orchestrator validates:

- release completion for the dispatched publish tag
- release type parity with `release_kind`
  - candidate expects `prerelease=true`
  - final expects `prerelease=false`
- additional finalization precondition: latest RC must already exist as a downstream pre-release

If any of these checks fail, the release workflow fails and rollback handling is evaluated by workflow conditions.

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
- Before final publish validation:
  - latest RC tag for the base version exists downstream as pre-release

### Failure Signals

Common failure patterns:

- no downstream release found for expected tag within timeout
- downstream release type mismatch (`prerelease` flag differs from expected)
- malformed/insufficient dispatch payload
- downstream workflow failure prior to release artifact publication
- workflow contract drift (required workflow ID missing on expected dispatch ref), which must fail fast in preflight

## Operational Verification

Examples for manual inspection:

```bash
gh -R vig-os/devcontainer-smoke-test run list --workflow repository-dispatch.yml --limit 5
gh -R vig-os/devcontainer-smoke-test run view <RUN_ID>
gh -R vig-os/devcontainer-smoke-test release view <TAG>
```

## Source of Truth

- Orchestrator logic: `.github/workflows/release.yml`
- Validation receiver template: `assets/smoke-test/.github/workflows/repository-dispatch.yml`

## Token Model for Downstream Write Paths

For downstream workflow templates used by this gate, repositories must provide both Commit and Release app credentials.

- Commit App token is required for protected branch writes performed by release preparation/finalization flows.
- Release App token is required for PR/release/workflow dispatch orchestration.

Using `github.token` for protected downstream write paths is not supported by this gate contract because branch rulesets may reject direct writes without app bypass.
