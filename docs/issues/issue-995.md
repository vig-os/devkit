---
type: issue
state: closed
created: 2026-07-13T07:12:37Z
updated: 2026-07-13T07:51:49Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/995
comments: 1
labels: chore, area:ci, effort:small, area:testing
assignees: none
milestone: none
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:53.303Z
---

# [Issue 995]: [Adopt actionlint for authored and per-mode rendered workflow templates](https://github.com/vig-os/devkit/issues/995)

### Description

Workflow YAML — both the devkit's own and, more critically, the per-mode
RENDERED scaffold output — is only yamllint- and grep-checked today. A
semantically broken rendered workflow (bad needs/output wiring, invalid
expression) would ship silently and only fail in a consumer repo. There is no
actionlint anywhere (flake, pre-commit, CI).

### Acceptance Criteria

- [ ] `actionlint` added to the flake toolchain (`nix/devtools.nix`) and
      pre-commit hook set (devkit repo workflows + `assets/workspace` templates
      where lintable as-is)
- [ ] bats fixtures run actionlint over each mode's rendered
      `.github/workflows/` tree (devcontainer / direnv / both / bare), extending
      the existing #854/#885 render assertions
- [ ] CI runs it (project-checks lane)

### Related Issues

Supports #991/#994 verification. Part of #988.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 07:51 AM_

Merged into the epic branch via #1001. actionlint 1.7.12 in the toolchain SSoT + devkit-own pre-commit hook + per-mode rendered-tree bats fixtures (devcontainer/direnv/bare/both/smoke-test). Verified locally in the dev-shell: 140/140 bats green, full hook suite green.

