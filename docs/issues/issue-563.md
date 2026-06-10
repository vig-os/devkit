---
type: issue
state: closed
created: 2026-06-09T08:24:27Z
updated: 2026-06-09T21:28:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/563
comments: 0
labels: priority:high, area:image, effort:medium, security, dependencies
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:24.702Z
---

# [Issue 563]: [security(deps): update vulnerable Python dependencies (idna, urllib3, Pygments, requests)](https://github.com/vig-os/devcontainer/issues/563)

## Bucket B - Vulnerable Python dependencies

Dependabot alerts on `uv.lock`, verified against current pinned versions on `dev` (2026-06-09).

### Still vulnerable - need bump (this repo)
| Package | Pinned now | First patched | Advisory | Severity |
| --- | --- | --- | --- | --- |
| urllib3 | 2.6.3 | 2.7.0 | GHSA-qccp-gfcp-xxvc | HIGH |
| urllib3 | 2.6.3 | 2.7.0 | GHSA-mf9v-mfxr-j63j | HIGH |
| requests | 2.32.5 | 2.33.0 | GHSA-gc5v-m9x4-r6x2 | MEDIUM |
| idna | 3.11 | 3.15 | GHSA-65pc-fj4g-8rjx | MEDIUM |
| Pygments | 2.19.2 | 2.20.0 | GHSA-5239-wwwm-4pmq | LOW |

### Already resolved (do not re-do)
- **pytest** -> fixed by #528 (now 9.0.3, the first patched version for GHSA-6w46-j5rx-g56g). The open Dependabot alert is stale and should auto-close on next scan.

### Action (this repo)
- [ ] `uv lock --upgrade-package urllib3 --upgrade-package requests --upgrade-package idna --upgrade-package pygments` (or let Renovate `pep621` open the PRs and merge them)
- [ ] Rebuild image and confirm the matching Trivy findings under `/root/.cache/uv/...` clear

### B2. Template source fix (downstream `vig-os/devcontainer-smoke-test`)

The same urllib3/idna advisories appear in the smoke-test repo's `uv.lock`. Additionally, the smoke-test has **many more** Dependabot HIGHs on the jupyter stack that are **not** in this repo's `uv.lock` but **are** real dependencies in consumer repos via the workspace template.

**Root cause:** `assets/workspace/pyproject.toml` pins:
- `jupyter==1.1.1`
- `ipykernel==7.2.0`

These pull the vulnerable transitive stack into downstream `uv.lock`:
- **notebook**: GHSA-mqcg-5x36-vfcg, GHSA-rch3-82jr-f9w9
- **jupyterlab**: GHSA-mqcg-5x36-vfcg, GHSA-37w4-hwhx-4rc4, GHSA-rch3-82jr-f9w9
- **jupyter-server**: GHSA-5mrq-x3x5-8v8f, GHSA-24qx-w28j-9m6p, GHSA-5789-5fc7-67v3, GHSA-qh7q-6qm3-653w
- **mistune**: GHSA-8mp2-v27r-99xp (+ several medium)

**Upstream vs downstream distinction:** In the devcontainer repo, jupyter packages only appear as transient uv-cache artifacts in Trivy (`/root/.cache/uv/archive-...`). In consumer repos (including smoke-test), they are **managed dependencies** seeded by this template `pyproject.toml`.

**Actions:**
- [ ] Bump/loosen `jupyter` and `ipykernel` pins in `assets/workspace/pyproject.toml` to versions that resolve the advisories above
- [ ] Bump this repo's `uv.lock` / `pyproject.toml` for urllib3, idna, requests, Pygments (same advisories as smoke-test)
- [ ] No manual downstream `uv.lock` step: the release dispatch re-runs `init-workspace.sh --smoke-test`, which deploys the fixed `pyproject.toml` and calls `just sync` to regenerate `uv.lock` automatically

### Context
`:latest` is release `0.3.4` (Apr 29); `dev` is ~70 commits ahead. Some dependency findings on `:latest` will also clear once `dev` is released and the nightly re-scans.

Refs: #512, #521, #529
