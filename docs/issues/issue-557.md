---
type: issue
state: closed
created: 2026-06-08T13:18:58Z
updated: 2026-06-08T14:25:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/557
comments: 1
labels: bug, priority:high, area:image, effort:small, area:testing, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-09T06:16:00.937Z
---

# [Issue 557]: [[BUG] Bump stale cargo-binstall image-test pin (version-approval gate)](https://github.com/vig-os/devcontainer/issues/557)

## Description

`test_cargo_binstall` in `tests/test_image.py` pins the expected version to `"1.19."`, but upstream released `cargo-binstall` `1.20.0`. The `Containerfile` installs the latest release at build time (`releases/latest`), so the image now ships `1.20.0` while the test still expects `1.19.`. This fails the `Image Tests` / `Test Summary` checks on open Renovate PRs (#553-556) and on `dev` itself.

This is **not** a design flaw — it is the intended version-approval gate. The same pattern applies to `gh`, `just`, `taplo`, and other tools installed from `releases/latest`: `EXPECTED_VERSIONS` pins are a deliberate tripwire. When upstream drifts past the pin, CI goes red and a human must consciously bump the pin and record it in the CHANGELOG (see PRs #547, #523, #525).

## Steps to Reproduce

1. Upstream publishes a new `cargo-binstall` release (e.g. `1.20.0`).
2. `Containerfile` installs the latest release at build time.
3. CI `Image Tests` job runs `test_cargo_binstall`.
4. The hardcoded `1.19.` pin no longer matches.

## Expected Behavior

Image tests fail when an upstream version drifts past the pin, prompting a human-approved bump of `EXPECTED_VERSIONS` and a CHANGELOG entry.

## Actual Behavior

```
AssertionError: Expected cargo-binstall 1.19., got: 1.20.0
assert '1.19.' in '1.20.0\n'
```

## Environment

- **OS**: CI (Ubuntu 24.04 host)
- **Container Runtime**: Podman (testinfra)
- **Image Version/Tag**: `ghcr.io/vig-os/devcontainer:dev`
- **Architecture**: AMD64

## Additional Context

Failing on PRs #553-556 ([example job](https://github.com/vig-os/devcontainer/actions/runs/27139267208/job/80100292218)).

Follow-up: a single-source-of-truth versions file (Containerfile + tests + README) with Renovate-managed bumps would make the approval moment a reviewable PR rather than post-hoc breakage. See the linked follow-up issue.

Acceptance criteria:

- [ ] Bump `EXPECTED_VERSIONS["cargo-binstall"]` from `1.19.` to `1.20.`
- [ ] Record the bump in `CHANGELOG.md`
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Possible Solution

Bump the stale pin to `1.20.` and document the version-gate intent. Longer term, centralize tool versions in a declarative file consumed by the Containerfile, tests, and README, with Renovate managing bumps.

**Changelog Category**: Fixed
---

# [Comment #1]() by [c-vigo]()

_Posted on June 8, 2026 at 01:42 PM_

Follow-up for centralized version management: #559

