---
type: issue
state: open
created: 2026-07-30T12:43:01Z
updated: 2026-07-30T12:43:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1305
comments: 0
labels: bug, priority:high, area:workspace, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-30T14:03:13.110Z
---

# [Issue 1305]: [fix(install): runtime auto-detection picks the runner's broken podman over docker (crun mismatch breaks consumer upgrade flows)](https://github.com/vig-os/devkit/issues/1305)

## Symptom

First live `devkit-upgrade` dispatch (devkit-smoke-test [run 30543470753](https://github.com/vig-os/devkit-smoke-test/actions/runs/30543470753), version=1.5.0): the App path worked end-to-end (fail-fast, token mint, adoption issue vig-os/devkit-smoke-test#310 opened by `app/vigos-devkit-upgrade`), then `install.sh --force` died at "Initializing workspace" with

```
Error: OCI runtime error: crun: unknown version specified
```

## Root cause

`detect_runtime()` prefers podman over docker. On `ubuntu-latest` both exist; runner images ≥ 20260726 pair preinstalled podman 5.8.4 with Ubuntu's stale crun (< 1.14.3), which rejects podman ≥ 5's OCI v1.2.x configs — the same regression as #1299, but on the **consumer** side, where devkit's `setup-env` crun pin (the #1299 fix) does not apply. The `devkit-upgrade.yml` comment even assumes docker ("docker is present on ubuntu-latest (install.sh auto-detects it)") — the detection contradicts it. As the runner fleet converges, every consumer's weekly upgrade run and the smoke deploy flow will fail at the install step.

## Fix

1. `detect_runtime()`: prefer **docker when its daemon responds** (`docker info`), falling back to podman — podman-only hosts (vigOS machines) unchanged; both-present hosts with a dead docker daemon still get podman. Explicit `--docker`/`--podman` flags keep overriding.
2. `devkit-upgrade.yml` template: pass `--docker` explicitly (self-documenting; GH runners always have docker).

Delivery: consumers curl `install.sh` from `main`, so the fix heals **all existing scaffolds** at the next promote with no re-scaffold. The 1.5.1 adoption dispatch then doubles as the live proof of the workflow's remaining push/PR legs (real version gap → full path).

Refs: #1299, #1296, #1302
