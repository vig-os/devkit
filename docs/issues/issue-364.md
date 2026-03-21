---
type: issue
state: closed
created: 2026-03-19T07:30:56Z
updated: 2026-03-20T08:37:13Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/364
comments: 1
labels: bug, priority:medium, area:ci, area:workflow, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:50.615Z
---

# [Issue 364]: [[BUG] Restore dispatch safeguards after smoke-test workflow sync](https://github.com/vig-os/devcontainer/issues/364)

## Description
After manually deploying the latest `repository-dispatch.yml` into `vig-os/devcontainer-smoke-test` ([PR #38](https://github.com/vig-os/devcontainer-smoke-test/pull/38)), two reliability safeguards were dropped relative to expected behavior:
- workflow-level per-tag concurrency
- shell `pipefail` protection before `curl | bash`

This creates risk of race conditions and less reliable failure detection during dispatch-driven deploy automation.

## Steps to Reproduce
1. Compare the synced workflow changes in smoke-test PR #38.
2. Observe removal of:
   - `concurrency.group: smoke-test-dispatch-${{ github.event.client_payload.tag || github.run_id }}`
   - `set -euo pipefail` in installer step before `curl ... | bash ...`
3. Trigger multiple dispatches with same tag close together, or simulate transient upstream fetch failure.

## Expected Behavior
Dispatch runs should serialize per tag, and shell pipelines should fail hard on upstream/download failures.

## Actual Behavior
Dispatch runs can overlap for the same tag and race on deploy branch/PR orchestration, and installer pipeline safety is weaker without `pipefail`.

## Environment
- **OS**: GitHub-hosted runner `ubuntu-22.04`
- **Container Runtime**: N/A (workflow execution context)
- **Image Version/Tag**: smoke-test dispatch workflow synced from development version `47952c9`
- **Architecture**: x86_64

## Additional Context
- Related PR and review comments:
  - https://github.com/vig-os/devcontainer-smoke-test/pull/38#discussion_r2958290852
  - https://github.com/vig-os/devcontainer-smoke-test/pull/38#discussion_r2958290868
- This issue is intentionally separate from #354.
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Possible Solution
- Re-introduce workflow-level concurrency in the dispatch workflow (group by tag with `run_id` fallback).
- Restore strict shell flags (`set -euo pipefail`) in the installer step.
- Validate with back-to-back same-tag dispatch runs.

## Changelog Category
Fixed
---

# [Comment #1]() by [c-vigo]()

_Posted on March 20, 2026 at 08:37 AM_

Investigated this and traced the safeguards in git history.

This is already solved in `vig-os/devcontainer` in the smoke-test dispatch template at:

- `assets/smoke-test/.github/workflows/repository-dispatch.yml`

### Solved by PRs

- **PR [#337](https://github.com/vig-os/devcontainer/pull/337)**  
  Added workflow-level per-tag concurrency:
  `concurrency.group: smoke-test-dispatch-${{ github.event.client_payload.tag || github.run_id }}`
  (commit [`6e9f60b`](https://github.com/vig-os/devcontainer/commit/6e9f60b1762aebceb20f18a1ef47a674d97e4690)).

- **PR [#334](https://github.com/vig-os/devcontainer/pull/334)**  
  Restored strict shell pipeline behavior in installer step:
  `set -euo pipefail` before `curl -sSf "${INSTALL_URL}" | bash ...`
  (commit [`0bcefb6`](https://github.com/vig-os/devcontainer/commit/0bcefb686be219b57cf6f2b689278385ee0c1055)).

- **PR [#342](https://github.com/vig-os/devcontainer/pull/342)**  
  Later workflow hardening/refinement retained those safeguards
  (commit [`3660a68`](https://github.com/vig-os/devcontainer/commit/3660a68acf01ab8201189fee8185e84b7fac13ae)).

### Conclusion

The issue here is downstream sync drift (manual smoke-test workflow sync dropped safeguards), not missing implementation in the canonical template.  
Resolution is to re-sync downstream `repository-dispatch.yml` from the PR-backed canonical version above.

