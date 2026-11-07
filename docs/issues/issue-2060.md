---
type: issue
state: open
created: 2026-11-06T15:50:41Z
updated: 2026-11-06T15:50:41Z
author: irenecortinovis
author_url: https://github.com/irenecortinovis
url: https://github.com/vig-os/devkit/issues/2060
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-07T08:37:42.843Z
---

# [Issue 2060]: [ci.yml: Resolve toolchain timeout of 2 min cancels runs on self-hosted runners](https://github.com/vig-os/devkit/issues/2060)

The generated `.github/workflows/ci.yml` (devkit 1.18.0) sets `timeout-minutes: 2` on the `Resolve toolchain` job. On self-hosted runners (`DEVKIT_CI_RESOLVE_RUNNER`, here ksb `ksb-morepet-small`), checkout plus toolchain resolution regularly takes longer under load. The job is cancelled, every dependent job is skipped, and the run reports failure; a rerun usually passes.

Seen 2026-11-06:
- MorePET/gPET-sim2listmode run 42243077820, attempt 1: `Resolve toolchain` cancelled after 2 m 05 s (15:36:30 → 15:38:35 UTC);
- MorePET/geddf-analysis run 42243018101, attempt 1: `Resolve toolchain` cancelled at 15:43:31 UTC.

The setup slowness this exposes is #1907, where the host Nix config overrides the runner's substituters.

Request: make the resolve timeout configurable through `.vig-os` (for example `DEVKIT_CI_RESOLVE_TIMEOUT_MINUTES`), or raise the default to something like 10 minutes when `DEVKIT_CI_RESOLVE_RUNNER` points to a self-hosted runner.

