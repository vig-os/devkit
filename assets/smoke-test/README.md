# devcontainer Smoke Test

This repository is a smoke-test workspace for the
[vig-os/devcontainer](https://github.com/vig-os/devkit) project.

Its purpose is to verify that the devcontainer template and the shipped CI
workflow run successfully on real GitHub-hosted runners, not only in local or
synthetic test environments.

## Why this repo exists

The main `vig-os/devcontainer` repository publishes template files under
`assets/workspace/`, including a CI workflow
(`assets/workspace/.github/workflows/ci.yml`).

This repository provides a real target where that template can be bootstrapped
and executed end-to-end so regressions are caught early, for example:

- broken GitHub Action pins
- runner environment changes
- dependency/tooling incompatibilities (for example `uv` changes)

## Scope

This repository is intentionally minimal. It is used to:

1. bootstrap a fresh workspace from the current devcontainer template
2. run the shipped CI workflow on pull requests
3. validate that expected jobs pass in GitHub Actions
4. host CI wiring experiments such as `repository_dispatch` listeners

## Relationship to `vig-os/devcontainer`

- **Source of truth for template**: `vig-os/devcontainer`
- **Execution/verification target**: this repository

Template or workflow changes should be made in
[`vig-os/devcontainer`](https://github.com/vig-os/devkit), then validated
here through a normal PR run.

## Automated deploy-and-test flow

For release validation, this repository receives `repository_dispatch` events
from `vig-os/devcontainer` and runs an automated deploy-and-test cycle:

1. validate the dispatch payload and extract the tag
2. deploy that tag with the online installer
3. create branch `chore/deploy-<tag>`, commit (always), and open a PR to `dev`
4. CI workflow (`ci.yml`) triggers on the PR
5. enable auto-merge once checks pass

This flow applies to both RC tags and final tags.

## Accepted Scorecard findings

This repository is an **unattended deploy-validation target**, so a few OpenSSF
Scorecard checks are intentionally accepted as won't-fix here (they do not apply
to real downstream projects, which should keep branch protection and review).
The full security policy and project-general accepted findings live in
[`SECURITY.md`](SECURITY.md); the smoke-test-specific ones are:

- **BranchProtectionID** / **CodeReviewID**: the automated deploy/release PRs are
  merged without human review by design. Requiring approving reviews would stall
  the `chore/deploy-<tag>` auto-merge and defeat the purpose of the smoke test.
- **PinnedDependenciesID** (`download-then-run`): the installer in
  `.github/workflows/repository-dispatch.yml` is fetched by immutable release
  tag, retried, and validated post-install. The `curl | bash` step cannot be
  pinned by hash and is accepted.

These are recorded as dismissed (won't-fix) code-scanning alerts with a comment
referencing the upstream tracking issue. See `vig-os/devcontainer` #568.

## Audit trail and status

There is no CHANGELOG in this repository.

Deployment history is tracked through:

- deploy PRs labeled `deploy`
- merge history on `dev`
- GitHub Actions runs attached to each deploy PR

## Recreate this smoke-test repo

If this repository is lost or needs to be rebuilt, recreate it from the
`vig-os/devcontainer` image/template:

1. Create a new empty repository (for example `vig-os/devkit-smoke-test`).
2. Clone it locally and run the installer with smoke-test assets enabled:

   ```bash
   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash -s -- --smoke-test .
   ```

3. Commit the generated files and push to `main`.
4. Open a PR and confirm the shipped CI workflow passes:
   - `.github/workflows/ci.yml`
5. Verify `.github/workflows/repository-dispatch.yml` exists and listens for
   `repository_dispatch` events.
