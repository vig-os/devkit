---
type: issue
state: open
created: 2026-10-30T00:48:59Z
updated: 2026-10-30T00:48:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1980
comments: 0
labels: chore, area:ci
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:24.045Z
---

# [Issue 1980]: [uv downloads metadata URL: offline guard against a future upstream file move](https://github.com/vig-os/devkit/issues/1980)

Follow-up from the review of PR #1978 (#1976).

1. **The test can't catch a future move.** `tests/test_uv_download_metadata.py` repeats the same `versionAtLeast "0.13.0"` rule as `flake.nix`. If uv moves `download-metadata.json` again, the test still passes and the URL quietly 404s again; only the arm64 job in `release.yml` would notice. Make the check confirm the file exists at the computed path in the packaged uv source: for example `builtins.pathExists "${pkgs.uv.src}/crates/<dir>/download-metadata.json"` in a flake check. It works offline, but it fetches the uv source at evaluation time, so weigh that cost and document the choice.
2. **Undocumented folder rule.** `docs/NIX.md:370` only says the URL is "pinned to the provisioned `uv` release". Document the version-dependent folder (`uv-python` before 0.13, `uv-python-managed` from 0.13).

Refs: #1976
