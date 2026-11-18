---
type: issue
state: open
created: 2026-11-06T10:39:03Z
updated: 2026-11-06T10:39:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2059
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-07T08:37:43.103Z
---

# [Issue 2059]: [ci.yml 'Devkit staleness' job fails on NixOS self-hosted runners: awk not on PATH (no toolchain setup step)](https://github.com/vig-os/devkit/issues/2059)

**Seen on:** gerchowl/mcpx PR #7 (devkit 1.19.0-rc1, direnv mode, `DEVKIT_CI_RUNNER=self-hosted,nix,anvil`), run https://github.com/gerchowl/mcpx/actions/runs/42155737148 on the g-fleet anvil runner (NixOS microVM, `extraPackages = [ pkgs.nix ]`).

**Failure:** step 'Compare DEVKIT_VERSION against the latest devkit release': `line 27: awk: command not found`, then `sort: write error`, exit 127. CI Summary fails as a result.

**Cause:** the `staleness` job runs on `fromJSON(needs.resolve-toolchain.outputs.runner-json)` (so it lands on the self-hosted runner), but has no `setup-devkit-toolchain` step. It runs with the bare host PATH, which on a minimal NixOS runner has no awk. Hosted ubuntu runners have awk, so consumers there never see it (gerchowl/nodd pins the same rc but runs hosted).

**Fix options:** (a) run the step inside the devkit toolchain like the other lanes; (b) drop awk/sort -V (e.g. a tiny Python/jq comparison, or bash-only); (c) pin the job to the hosted runner like release/sync. Same class as #1864 (tac on darwin): workflows that assume host coreutils on self-hosted runners.

**Acceptance:** the staleness job passes on a NixOS self-hosted runner without host coreutils/gawk.
