---
type: issue
state: open
created: 2026-10-11T21:49:07Z
updated: 2026-10-11T21:49:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1864
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:44.137Z
---

# [Issue 1864]: [setup-devkit-toolchain is not macOS-portable: `tac` at action.yml:263 kills every direnv lane on a darwin self-hosted runner](https://github.com/vig-os/devkit/issues/1864)

Routing a consumer's direnv CI lanes onto a self-hosted **macOS** runner via `DEVKIT_CI_RUNNER` (#1173) fails in `setup-devkit-toolchain` for every lane, at the same line.

## Symptom

`gerchowl/pidgy` on devkit 1.18.0, `DEVKIT_MODE=direnv`, `DEVKIT_CI_RUNNER=self-hosted,macOS,ARM64,sage`, runner = an ephemeral macOS 26.6.2 arm64 VM with Nix installed:

```
/Users/admin/actions-runner/_work/_temp/cb28abcc-….sh: line 87: tac: command not found
##[error]Process completed with exit code 127
##[end-action id=__self.__run_3;outcome=failure;duration_ms=326099]
```

Identical failure in `Lint & Format`, `Tests` and `Commit Messages` — the three lanes that resolve `runs-on` from `runner-json`. Note the `duration_ms`: the dev shell built **successfully** in ~5.5 minutes first. The toolchain provisioning works on darwin; only this one line does not.

## Cause

`actions/setup-devkit-toolchain/action.yml:263`:

```sh
printf '%s\n' "$STORE_BINS" | tac >> "$GITHUB_PATH"
```

`tac` is GNU coreutils. macOS does not ship it. And this step runs on the **host**, outside the dev shell, so nixpkgs' coreutils is not on `PATH` — the action cannot rely on the shell it is in the middle of provisioning.

## Why it can't just be dropped

The comment above it (lines 253-262) is right and the reversal must survive any fix:

> Reversed on purpose: the runner *prepends* every `GITHUB_PATH` line to PATH in file order […] fatal for a stdenv toolchain: raw gcc then shadows gcc-wrapper (likewise binutils) and every C build fails with `cannot find Scrt1.o` / `cannot find -lc` while the same build is green locally under `nix develop` (#1351, vig-os/h5v#2).

So this needs a portable line reversal, not a removal.

## Suggested fix

POSIX, works identically on GNU and BSD/macOS:

```sh
printf '%s\n' "$STORE_BINS" | sed '1!G;h;$!d' >> "$GITHUB_PATH"
```

or, if readability is preferred:

```sh
printf '%s\n' "$STORE_BINS" | awk '{ a[NR] = $0 } END { for (i = NR; i > 0; i--) print a[i] }' >> "$GITHUB_PATH"
```

`tail -r` also works on macOS but **not** on GNU, so it would just invert the platform that breaks.

## Worth a sweep

This is the only `tac` in the action, but the same class of assumption (GNU-only host tools in steps that run *outside* the dev shell) would fail the same way. `DEVKIT_CI_RUNNER` makes darwin runners reachable, so these are now live paths. Candidates worth grepping for: `readlink -f`, `sed -i` without a suffix, `date -d`, `stat -c`, `grep -P`, `base64 -w`, `mktemp --tmpdir`.

Filed alongside a second darwin blocker: the `scaffold-drift` lane shells out to `docker` and runs the Linux devkit image, which cannot work on a macOS runner at all.
