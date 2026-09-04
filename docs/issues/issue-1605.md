---
type: issue
state: open
created: 2026-09-03T09:25:57Z
updated: 2026-09-03T09:25:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1605
comments: 0
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-04T07:09:27.155Z
---

# [Issue 1605]: [[FEATURE] vigos.multiplexer: keybindings and terminal defaults for the org tmux config](https://github.com/vig-os/devkit/issues/1605)

## Description

`vigos.multiplexer` today sets five options (`keyMode`, `historyLimit`, `mouse`,
`escapeTime`, `baseIndex`) and **no keybindings**, and leaves
`programs.tmux.terminal` at the home-manager default. Add a small set of
keybindings and terminal defaults so any host that enables the module gets a
usable tmux out of the box, instead of every consumer re-deriving the same
`extraConfig`.

## Problem Statement

The concrete trigger: `prefix + X` — kill the current session, i.e. "close this
project" — exists only in a downstream consumer's personal `extraConfig`. On a
host running the module bare (a shared remote development guest, a devcontainer)
the key is simply unbound, so a habit built on one machine silently does nothing
on the next. `prefix + x` still works there, because kill-pane is a tmux
default; `X` is not. The same asymmetry applies to cwd-preserving splits,
contiguous window numbers, and truecolor.

The terminal default is the sharpest of these:

```console
$ nix eval .#homeConfigurations."ci-full-x86_64-linux".config.programs.tmux.terminal
"screen"
```

`screen` advertises 8 colors and no italics. Everything the org ships that draws
color — starship, neovim (`vigos.editor`), delta, lazygit, `gh-dash` — renders
degraded the moment it runs inside tmux, on every host, which is precisely the
case the module exists to standardise.

And since `vigos.sesh` makes the *session* the unit of work, it is worth the
module binding something for ending one.

## Proposed Solution

Extend `nix/home/multiplexer.nix`. Options stay `mkDefault`; keybindings append
to `programs.tmux.extraConfig`, which merges — and tmux takes the *last* binding
of a key, so a consumer keeps the existing override seam (`lib.mkAfter`) that
`vigos.sesh` already uses for `bind o`.

**1. Session kill — the trigger**

```tmux
bind-key X confirm-before -p "kill session '#S'? (y/n)" kill-session
```

`X` is unbound in stock tmux, so this takes nothing away, and `confirm-before`
keeps a stray prefix from destroying a project's layout.

**2. Terminal defaults**

```nix
terminal = lib.mkDefault "tmux-256color";
```

```tmux
set -ga terminal-overrides ",*256col*:Tc"
```

**3. Core ergonomics**

```tmux
bind '"' split-window -v -c "#{pane_current_path}"
bind %   split-window -h -c "#{pane_current_path}"
bind c   new-window -c "#{pane_current_path}"
set -g renumber-windows on
set -g focus-events on
```

Focus events are what let neovim's `autoread`/autosave and vim-tmux-style
integrations notice focus changes.

**4. Clipboard and vi copy-mode**

```tmux
set -g set-clipboard on
bind-key -T copy-mode-vi v send-keys -X begin-selection
bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel
```

OSC 52 matters most for remote work: a yank inside tmux on a remote development
host reaches the local clipboard with no X forwarding. `v`/`y` match the
module's own `keyMode = "vi"`, which stock tmux does not bind in copy mode.

**5. Session ergonomics**

```tmux
set -g detach-on-destroy off
set -g set-titles on
set -g set-titles-string "#S"
```

`detach-on-destroy off` pairs with both `X` and sesh: killing one project
switches to another live session instead of dropping to a bare shell, and if it
was the last session the client still detaches. Titles make several terminal
windows distinguishable by project rather than all showing the launch command.

**6. Vim pane navigation**

```tmux
bind h select-pane -L
bind j select-pane -D
bind k select-pane -U
bind l select-pane -R
```

Flagged for review: this is the **only** item that removes a default —
`prefix + l` is `last-window` in stock tmux. Coherent with the module's vi key
mode, but drop it or rebind `last-window` elsewhere if the trade isn't wanted.

## Alternatives Considered

- **Leave it downstream (status quo).** Every consumer re-derives the same
  `extraConfig`, and the fleet's shared hosts get none of it — which is the bug
  report that started this.
- **Put the keybindings in `vigos.sesh`.** Wrong home for most of them; only
  `detach-on-destroy` is sesh-flavoured, and even that is plain tmux behaviour.
- **A per-group enable option** (`vigos.multiplexer.keybindings.enable`, …).
  YAGNI: `extraConfig` is already the override seam (last binding wins) and
  every option here is `mkDefault`.

## Additional Context

- Module today: `nix/home/multiplexer.nix` — options only, no `extraConfig`.
- `nix/home/sesh.nix` already appends `bind o display-popup -E "sesh-picker"` to
  the same `extraConfig` via `lib.mkAfter`; this uses the identical merge point.
- Testing: `tests/test_flake_checks.py` already evaluates
  `homeConfigurations."ci-full-x86_64-linux".config` in one cached slice. The
  new settings and bindings are assertable from that same eval
  (`programs.tmux.terminal`, `programs.tmux.extraConfig`), so this need not land
  as an untested config-only change.

## Impact

- **Who benefits:** every host enabling `vigos.multiplexer` — shared remote
  development guests, devcontainers, and personal machines that currently
  duplicate this config by hand.
- **Compatibility:** backward compatible with two behaviour caveats, both from
  group 5–6: `prefix + l` changes from `last-window` to `select-pane -R`, and
  `detach-on-destroy off` changes what happens to a client after its session
  ends. Everything else is purely additive or a `mkDefault` a consumer can
  already override.
- **semver:** minor.

## Changelog Category

Added

