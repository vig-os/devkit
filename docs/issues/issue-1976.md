---
type: issue
state: open
created: 2026-10-30T00:32:38Z
updated: 2026-10-30T00:32:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1976
comments: 0
labels: bug, area:ci
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:24.656Z
---

# [Issue 1976]: [uv 0.13: UV_PYTHON_DOWNLOADS_JSON_URL points at a path that 404s (arm64 release build fails)](https://github.com/vig-os/devkit/issues/1976)

Found by the 1.18.1 candidate run (https://github.com/vig-os/devkit/actions/runs/40979727177), job "Build and Test (arm64)".

**Symptom.** `uv sync` fails with exit 2:

```
error: Error while fetching remote python downloads json from `https://raw.githubusercontent.com/astral-sh/uv/0.13.4/crates/uv-python/download-metadata.json`
  cause: HTTP status client error (404 Not Found)
```

**Cause (to confirm).** The #1912 nixpkgs-unstable bump moved uv from 0.12.17 to 0.13.4. `UV_PYTHON_DOWNLOADS_JSON_URL` is derived from the uv version and forwarded by `.github/actions/setup-env/action.yml` (and by the consumer `setup-devkit-toolchain` action). Under 0.12.17 it pointed at `.../uv/0.12.17/crates/uv-python/download-metadata.json`. That path no longer exists at the 0.13.4 tag. dev runs uv 0.13.4 too, but its amd64 CI apparently never needs a Python download, so this is latent on dev.

**Expected.** The URL resolves for the shipped uv version, or the mechanism stops depending on an upstream repo path, with a test that fails when the URL 404s or mismatches the uv version. It affects devkit's own CI and the consumer `setup-devkit-toolchain` action.
