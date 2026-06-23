---
type: issue
state: open
created: 2026-02-20T10:34:52Z
updated: 2026-06-23T06:56:47Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/109
comments: 1
labels: discussion, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:58.288Z
---

# [Issue 109]: [[DISCUSSION] Optimize CI pipeline for PRs to dev — full security scan on every PR?](https://github.com/vig-os/devcontainer/issues/109)

### Description

Should the full CI pipeline (including security scans and other long-running jobs) run on every PR to `dev`, or can we slim it down to "it builds & tests pass" for faster feedback?

Currently, PRs to `dev` run the complete CI suite including security scanning, which adds significant time. With the goal of faster PR turnaround, we should discuss whether that's necessary or if a smarter approach exists.

### Context / Motivation

CI runs on PRs to `dev` take a long time, partly due to security scans and other heavyweight checks. For a branch that primarily serves as an integration target (not production), this slows down the development loop without a clear proportional benefit. The question is whether the full suite is justified for every PR to `dev` or only for PRs into `main`.

### Options / Alternatives

1. **Minimal CI on PRs to `dev`** — Only run build + test. Reserve security scans and other heavyweight checks for PRs into `main`.
2. **Smart/conditional CI** — Detect what changed and skip security scans when no new packages or version updates are present. E.g., only trigger security scanning when `requirements.txt`, `Dockerfile`, lock files, or similar dependency files change.
3. **Keep full CI everywhere** — Accept the longer times for maximum safety at every stage.

### Open Questions

- Is "it builds & tests pass" sufficient confidence for merging into `dev`?
- Should security scanning only gate PRs into `main`?
- Can we use path-based triggers (e.g., changes to dependency files) to conditionally run security scans on `dev` PRs?
- Are there other long-running CI jobs besides security that could be deferred to the `main` gate?

### Related Issues

_None yet_

### Changelog Category

No changelog needed
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

The Trivy scan-category consolidation discussed here overlaps the CVE rework in #637 (vulnix + SBOM, part of #625); worth resolving together.

