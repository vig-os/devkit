---
type: issue
state: open
created: 2026-11-04T10:14:20Z
updated: 2026-11-04T10:28:16Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2037
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:50.628Z
---

# [Issue 2037]: [test: SSH GitHub auth integration test flakes on a hard 10s timeout](https://github.com/vig-os/devkit/issues/2037)

## Problem

`tests/test_integration.py::TestDevContainerCLI::test_ssh_github_authentication` runs `ssh -T git@github.com` inside the devcontainer under a hard 10 s `dc_exec` timeout. On 2026-11-04 it failed twice within about 20 minutes with `subprocess.TimeoutExpired ... timed out after 10 seconds`:

- release-branch PR CI (Integration Tests, amd64), run 41810176216; passed on rerun
- `release.yml` candidate run 41811847009, Build and Test (arm64); amd64 was cancelled by fail-fast

It did not fail in the previous 25 CI runs. The likely cause is slow GitHub SSH from the runners. The test measures a third-party network round trip, and a hard 10 s budget with no retry makes a release candidate depend on github.com SSH latency.

## Proposal

- Give the SSH probe its own, longer timeout (for example 30 s) plus `-o ConnectTimeout=` and a single retry on timeout. Keep failing on a real auth failure (`Permission denied`).
- Alternatively, treat a network timeout (as opposed to an auth failure) as `pytest.xfail`/skip with a clear reason.

## Acceptance

- A slow or timed-out SSH handshake no longer fails Integration Tests or the release Build and Test job.
- A wrong or missing key still fails the test.

---

# [Comment #1]() by [gerchowl]()

_Posted on November 4, 2026 at 10:28 AM_

Update: all three timeouts (09:5x to 10:17Z on 2026-11-04) fall inside the GitHub incident affecting Git Operations, Pull Requests and Actions (investigating since 09:53Z), which also caused 502s on PR merges and `Internal Server Error` on branch pushes in this repo. The test is most likely not flaky in normal conditions. The open question remains whether a release gate should hard-fail on github.com SSH availability. Moving this out of the 1.19.0 critical path; to be handled on dev.

