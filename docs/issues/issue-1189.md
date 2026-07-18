---
type: issue
state: open
created: 2026-07-17T14:55:42Z
updated: 2026-07-17T14:55:42Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1189
comments: 0
labels: bug, priority:blocking, area:ci, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:24.374Z
---

# [Issue 1189]: [setup-devkit-toolchain env forward corrupts GITHUB_ENV via shellHook stdout banner](https://github.com/vig-os/devkit/issues/1189)

## Description

1.4.0-rc2 consumer validation (org-config PR vig-os/org-config#54, sync-issues-action PR vig-os/sync-issues-action#143) fails on every direnv-mode host CI job at "Set up devkit toolchain":

```
Forwarded 31 dev-shell shellHook env var(s) to GITHUB_ENV.
##[error]Unable to process file command 'env' successfully.
##[error]Invalid format 'devcontainer dev environment loaded (nix)'
```

## Root cause

The #1180 shellHook env forwarding captures the dev-shell environment via

```bash
nix develop --profile ... --command env -0 > "$RUNNER_TEMP/devkit-devshell-env"
```

i.e. it redirects the **whole stdout of `nix develop`** into the dump file. But the devkit-scaffolded flake `shellHook` echoes a banner to stdout (`echo "devcontainer dev environment loaded (nix)"`), which lands *before* the `env -0` output in the same stream. The first NUL-delimited record becomes `<banner>\n<FIRST_VAR>=<value>`; since the host dump has no banner, the record is classified "changed" and forwarded, writing a heredoc whose name line contains the bare banner text — which GitHub's env file-command processor rejects, failing the job.

Both the banner and the action are devkit-managed, so **every direnv-mode consumer on 1.4.0 breaks** and cannot fix it locally. rc2's own smoke test missed it because the smoke-test consumer is container-mode (the direnv preamble never runs).

## Fix

1. Dump the environment to a file **inside** the dev-shell command instead of capturing stdout: `nix develop ... --command bash -c 'env -0 > "$1"' _ "$RUNNER_TEMP/devkit-devshell-env"` — banner stdout stays on the job log, the dump stays clean.
2. Defense in depth: skip records whose name is not a valid env identifier (`^[A-Za-z_][A-Za-z0-9_]*$`) so a corrupted record can never reach GITHUB_ENV again.

TDD: extend `tests/test_setup_toolchain_env.py` — make the stub `nix` emit the banner on stdout like the real flake does; assert the banner never reaches GITHUB_ENV and the first env record survives intact.

Fix targets `release/1.4.0` per the RC-validation runbook (like #1187); rc3 follows.

## Impact

Blocks 1.4.0 — all three Wave-1 consumer validation PRs are red on this.
