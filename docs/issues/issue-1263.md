---
type: issue
state: closed
created: 2026-07-24T08:23:15Z
updated: 2026-07-25T15:02:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1263
comments: 1
labels: bug, priority:medium, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-26T05:38:57.399Z
---

# [Issue 1263]: [Consumer adoption bumps .vig-os but not the vigos flake pin — dev-shell toolchain lags a release behind](https://github.com/vig-os/devkit/issues/1263)

## Description

The devkit adoption/upgrade flow (install.sh scaffold + lane bump commits) advances the `.vig-os` `DEVKIT_VERSION` pin, which governs the **image/scaffold**, but never touches the consumer's `flake.lock` — which governs the **direnv dev shell** (the `vigos` input floats on the default branch but is locked at whatever rev the last `nix flake update vigos` saw).

All five 1.4.1 consumers currently show this skew: `.vig-os` says `1.4.1` while `flake.lock` pins `vigos` at `d16541f5` (the 1.4.0 release commit). Their shells run 1.4.0 `vig-utils` and hook sets.

## Live symptom (2026-07-24, org-config)

org-config committed `.github/label-taxonomy.local.toml` (the #1254 extension) and ran `setup-labels --prune --dry-run` from its own dev shell: the 1.4.0 tool ignored the extension and planned to DELETE the repo's `drift`/`critical`/`change-request` labels. The same command via the devkit 1.4.1 shell read the extension and planned only the missing `create inventory`. A consumer following the documented workflow would have silently destroyed its own labels one release after the protecting feature shipped.

## Expected

Adopting devkit X.Y.Z should advance the shell toolchain too. Options to triage:
- scaffold/upgrade runs (or instructs) `nix flake update vigos` when the workspace flake's `vigos` input floats and lags `DEVKIT_VERSION`;
- a post-scaffold warning comparing the locked `vigos` rev's release against `DEVKIT_VERSION` (cheap, no behavior change);
- document the `flake update` step in MIGRATION.md's upgrade checklist (the sync-issues 1.3.1 adoption already fixed this drift by hand once).

## Impact

Every direnv consumer, every release: flake-shipped fixes (vig-utils scripts, hook sets, mkProjectShell changes) do not reach consumers until someone remembers a manual `nix flake update vigos`.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 25, 2026 at 03:02 PM_

Implemented in one pass on dev via PR #1272 (merge ead23720): (1) mkProjectShell shell-entry version-skew guard — the shellHook compares the flake's own release (repo-root .vig-os at the locked input rev) against the workspace pin and warns with the `nix flake update vigos` remedy; silent on matching versions, `-rc*` pins, and bare consumers. (2) `install.sh --force` now advances a floating vigos flake lock host-side for direnv/both consumers with an existing flake.lock (non-fatal when nix is missing/offline — manual step printed). (3) MIGRATION.md documents the two coupled delivery channels in the Updating checklist and corrects the floating-input exemption; the #1093 comment premise is fixed likewise.

Ships with the next release. Note the guard itself is flake-delivered, so the five current consumers first see it after their next lock advance — which the upgrade path now performs for them.

