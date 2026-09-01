---
type: issue
state: closed
created: 2026-08-31T09:46:36Z
updated: 2026-09-01T14:11:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1585
comments: 1
labels: feature, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.13.0
projects: none
parent: none
children: none
synced: 2026-09-01T15:12:54.345Z
---

# [Issue 1585]: [[FEATURE] vigos.sesh: remote project seeds and a runner-aware picker](https://github.com/vig-os/devkit/issues/1585)

## Description

`vigos.sesh` assumes every project lives on the machine running the picker. Add an optional `remotes` inventory — project × host × path — so a seed can also be opened over SSH, with the picker gaining a second stage that only appears when a project actually has more than one location.

Empty inventory (the default) must leave today's behaviour bit-for-bit unchanged.

## Problem Statement

Work does not all happen locally: a repo may be checked out on a workstation, a build host, or a lab machine, and the useful session is wherever the work already is. Today `vigos.sesh` can only connect locally, so reaching a remote checkout means dropping out of the picker entirely — `ssh`, then `tmux new -A` by hand, remembering the path, and losing the one-keypress flow the module exists to provide.

The reconnect case is the sharper one. A long-running session left on a remote host is exactly what you want to return to, and returning to it should not cost more keystrokes than starting a fresh local one.

This also blocks a consumer migration: a downstream config carrying its own remote-aware picker cannot adopt `vigos.sesh`, because **both ship a binary named `sesh-picker`** and collide at build time. The remote capability has to exist here before that config can drop its own module ([c-vigo/vigo-nixos#18](https://github.com/c-vigo/vigo-nixos/issues/18)).

## Proposed Solution

**1. `vigos.sesh.remotes`** — a list of `{ project, host, path }`:

- `project` matches a `sessions[].name` (or stands alone, for a host-access entry that is not a project).
- `host` is an `~/.ssh/config` alias — no connection details in the module.
- `path` is the project root on that host.

One entry per project × host, so a project may list several. The module renders it to a data file beside `sesh.toml`; the option is the *type*, while the inventory itself stays in the consumer's config (ADR placement rule — no host lists in the devkit).

**Deliberately just host + path.** An earlier per-host `useSesh`-style capability flag was dropped: the dispatch below detects capability at connect time, so a flag would be a second source of truth that goes stale.

**2. Two-stage picker.** Stage 1 picks the project; stage 2 picks the *runner* (local, or one of the hosts) — and appears **only** when there is a real choice. A purely local project, or a single-runner entry, keeps the current one-keystroke flow. The last-used runner per project is remembered and pre-selected, so `Enter Enter` returns to wherever the session was left.

**3. `sesh-remote-connect`** — attach-or-create over SSH, with capability probed and acted on in the *same* round trip:

1. `sesh-layout` on the remote PATH → full layout (its presence is an all-or-nothing test for a provisioned host; remote `sesh` is not needed, since tmux runs the layout as the session's startup command on create and ignores it on attach)
2. tmux only → persistent blank session
3. neither → plain login shell at the path, after an explicit warning that nothing survives a disconnect

`tmux new -A` makes it idempotent — attach if present, create otherwise — which is what allows "leave it running, reattach later" with no local state.

## Alternatives Considered

- **A per-host capability flag** in the inventory — rejected above: the single-round-trip probe is always current, a flag is not.
- **Requiring sesh on the remote** — unnecessary and a much heavier provisioning bar; tmux is the only real requirement (`tmux new -A`).
- **Leaving it to the consumer** — the status quo, and the thing that forces a competing `sesh-picker` and blocks adoption.
- **`sesh`'s own remote support** — not equivalent: the tiered degrade, the runner memory, and the nested-tmux escape hatch below are the parts that make this usable day to day.

## Additional Context

Field-proven in a consumer config since 2026-08-10 before being proposed here — the same prototype-then-parameterize path `vigos.sesh` itself took.

Two implementation details worth carrying up, because both were bugs first:

- **A remote tmux must not nest inside the local one.** When the picker is invoked from a tmux popup, the SSH client needs its own terminal window rather than a nested server. That escape hatch spawns a terminal — which means the terminal is **not** hardcodable here and needs an option (or a sensible default), since it is squarely personal-config territory.
- **`TERM` must be forced to something every remote terminfo database has.** A modern local terminal's own `TERM` is frequently unknown off-NixOS, and the session comes up broken.

Non-interactive SSH shells do not load home-manager session variables, so the dispatch has to put the per-user Nix profile bin directories on `PATH` itself before probing.

## Impact

- **Backward compatible.** With `remotes = []` — the default — no data file is meaningful, stage 2 never appears, and the picker behaves exactly as it does today. Existing consumers see no diff.
- Unblocks dropping a downstream personal `sesh.nix` in favour of `vigos.sesh` (the `sesh-picker` collision above).
- Benefits anyone whose projects are not all on one machine — the multi-host case the module currently cannot express.
- Test surface: `tests/test_flake_checks.py` already asserts the sesh contract; this adds the rendered inventory, the empty-inventory no-op guarantee, and the option schema. The interactive picker paths are shell and are not unit-testable here.




---

# [Comment #1]() by [c-vigo]()

_Posted on September 1, 2026 at 09:06 AM_

Solved by #1591, merged to dev. vigos.sesh.remotes (project × host × path, rendered to remotes.tsv only when populated — empty default is a bit-for-bit no-op), the two-stage runner picker with last-used-runner memory, and sesh-remote-connect with the single-round-trip tiered capability probe are all in. The nested-tmux escape hatch is the new vigos.sesh.remoteTerminal option (null default opens a local tmux window; set e.g. "ghostty -e" for an own-window client). Ships in the next minor together with #1586, making the downstream sesh-picker/gh-dash-repo migration atomic.

