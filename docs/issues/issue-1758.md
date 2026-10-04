---
type: issue
state: closed
created: 2026-09-28T21:44:59Z
updated: 2026-10-03T18:47:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1758
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-04T08:17:15.131Z
---

# [Issue 1758]: [DEVKIT_SYNC_TARGET mirror mode has no fold-back when the release feature group is disabled — the archive diverges permanently](https://github.com/vig-os/devkit/issues/1758)

## Summary

`DEVKIT_SYNC_TARGET` mirror mode and `DEVKIT_FEATURES_DISABLED=release` are individually supported but
silently incompatible. The mirror's only path back into the mainline is the fold rendered into
`release-core.yml` (#1424), and a release-less consumer has no `release-core.yml`. Setting a mirror
target there means the issue/PR archive leaves the trunk **permanently**, with nothing that says so.

## Mechanism

`render_sync_settings()` in `assets/init-workspace.sh` does two things for a non-empty
`DEVKIT_SYNC_TARGET`: it retargets `sync-issues.yml` and injects the bootstrap step (both
unconditional), and then it renders the fold — guarded on the file existing:

```bash
# Mirror mode makes the release train the mirror's integration point (#1424).
local rc="$WORKSPACE_DIR/.github/workflows/release-core.yml"
if [[ -f "$rc" ]]; then
    ...  # sync dispatch retarget + "Stage sync mirror archive for fold" steps
fi
```

The comment states the intent plainly — *"Absent when the release feature is disabled — the `-f` guard
skips it then."* — so the guard is deliberate. What is missing is any consequence: with `release` in
`DEVKIT_FEATURES_DISABLED` the scaffold prunes `release-core.yml`, the `-f` test fails, and mirror
mode is rendered **without an integration point**. The scaffold prints nothing, and the only
description of the tradeoff lives in an `.vig-os` comment that says the mirror "diverges permanently
and is never merged back (each sync regenerates full state)" — which reads as an acceptable property
of mirror mode rather than as a capability the release group is carrying.

The two knobs are also documented independently, so nothing in `.vig-os` connects them.

## Why "each sync regenerates full state" does not make it safe

That claim holds for the mirror branch itself, and it is what makes the divergence tolerable *when the
fold exists*. Without a fold, it means something different: the trunk keeps whatever copies it had at
the moment of the switch, forever, and they are progressively more wrong. Anyone reading
`docs/issues/` on the trunk sees a stale snapshot with no marker. In vig-os/tessera that is 181
tracked files under `docs/issues/` and `docs/pull-requests/`.

## Suggested fix

Pick one; the first is cheapest and probably sufficient:

1. **Refuse or warn loudly at scaffold time.** When `DEVKIT_SYNC_TARGET` is set and `release` is in
   `DEVKIT_FEATURES_DISABLED`, print a prominent notice (or abort, matching how an unknown feature
   name aborts) saying the mirror will never be folded back and the trunk's archive will freeze. This
   is a one-line composition check next to the existing `feature_disabled sync-issues` notice, which
   already sets the precedent for exactly this shape of guard.
2. **Provide a release-independent fold.** A small scheduled or post-sync job that opens a PR from the
   mirror's archive to the trunk, so a release-less consumer still has a path back. More work, and it
   reintroduces the protected-branch problem mirror mode exists to dodge — though via a reviewable PR
   rather than a direct push, which is the acceptable form.
3. **Document the coupling** in `.vig-os` on both keys, so `DEVKIT_SYNC_TARGET` says it depends on the
   `release` group for fold-back and `DEVKIT_FEATURES_DISABLED` says disabling `release` removes it.

## Context

Hit in vig-os/tessera#362. That repo is `DEVKIT_FEATURES_DISABLED=release` (cargo-dist owns
`release.yml`, see tessera#441) and is adopting mirror mode because `dev` carries classic branch
protection requiring a status check, which refuses the sync job's direct API push. It is going ahead
with the permanent divergence as a deliberate, documented interim — but it had to be discovered by
reading `init-workspace.sh`, which is the part worth fixing.
---

# [Comment #1]() by [gerchowl]()

_Posted on September 28, 2026 at 10:00 PM_

Small documentation inaccuracy in the same area, noticed while writing the consumer-side notice for
this.

The `DEVKIT_SYNC_TARGET` comment in the scaffolded `.vig-os` says:

> the mirror diverges permanently and is never merged back (each sync run regenerates full state)

The parenthetical does not match the workflow. The sync is **incremental**: `Sync Issues and PRs`
passes `state-file: .sync-state/last-sync.txt` and `updated-since`, so a run writes only what changed
since the last watermark. `Compute incremental cutoff` widens that to a bounded 14-day look-back
*only* on a cache miss, and a full rebuild happens solely via the `force-update: true` dispatch input.

It matters because "regenerates full state" reads as self-healing, and is presumably part of why the
permanent divergence looks acceptable — if every run rewrote everything, a mirror that fell behind
would repair itself. An incremental sync can instead carry a permanent gap, which is exactly the
failure mode in #1757 (the watermark advancing past a delta whose push failed). The two together mean
a mirror can be missing items with nothing to recover them.

Suggest dropping the parenthetical or replacing it with something like "each sync run writes the items
changed since the last watermark; `force-update` rebuilds from scratch".

---

# [Comment #2]() by [c-vigo]()

_Posted on October 3, 2026 at 06:47 PM_

Fixed by #1809 (merged to dev): the scaffold now prints a notice when DEVKIT_SYNC_TARGET is set with `release` disabled, and the docs no longer claim each sync regenerates full state. A release-independent fold-back (option 2) was left out of scope; file separately if a release-less consumer needs it.

