---
type: issue
state: closed
created: 2026-09-28T18:12:15Z
updated: 2026-09-30T20:16:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1753
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-01T08:40:58.913Z
---

# [Issue 1753]: [[BUG] vigos.multiplexer: detach-on-destroy off re-attaches a client to an already-attached session](https://github.com/vig-os/devkit/issues/1753)

## Summary

`nix/home/multiplexer.nix:67` sets `detach-on-destroy off`. For a consumer that
runs **one terminal window per project** — each window launching its own
attach/picker — killing a session does not end that window. tmux switches the
orphaned client to the most recently active remaining session, which already has
a window of its own. The result is two windows showing one project, and the
window that was meant to close stays open.

## Reproduce

1. Enable `vigos.multiplexer`; open three sessions, each attached from its own
   terminal window (so no session is left detached).
2. `prefix + X` (the module's own kill-session binding, #1605) in one of them,
   confirm.
3. The session dies, but its window reappears attached to one of the other two
   projects — now displayed twice. Expected: that window closes.

## Why `off` is the wrong value, not just an unlucky one

`no-detached` differs from `off` in exactly one case, and it is the broken one:

| Remaining sessions | `off` | `no-detached` |
| --- | --- | --- |
| some sitting detached | switch to it | switch to it — identical |
| all already attached elsewhere | re-attach onto a session already on screen | detach, the window closes |
| none | detach | detach — identical |

Everything the current comment claims for `off` ("switches to another live
session instead of dropping to a bare shell; the client still detaches if it was
the last one") stays true under `no-detached`. Only the duplicate-attach case
changes.

It is also inconsistent with the line right below it: `set-titles` is justified
in the same comment block as making *"several terminal windows distinguishable
by project"* — i.e. the module already assumes the multi-window, multi-client
workflow that is precisely where `off` misbehaves.

## Proposed fix

```diff
-      set -g detach-on-destroy off
+      set -g detach-on-destroy no-detached
```

Single-host/single-client consumers (a devcontainer, an SSH'd guest with one
attached client and other sessions detached) see no change at all.

The comment above it wants a small edit too, since the behaviour is now
conditional: switch to a detached session if one exists, otherwise detach.

## Workaround

Re-set the option after the module's block from the consumer's own
`extraConfig`, ordered later. The override can be dropped once this lands.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 30, 2026 at 08:16 PM_

Fixed on `dev` by #1792 (964a49da): `detach-on-destroy no-detached`. The consumer-side `extraConfig` override can be dropped once this release is adopted.

