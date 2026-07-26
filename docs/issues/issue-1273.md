---
type: issue
state: open
created: 2026-07-26T06:36:38Z
updated: 2026-07-26T06:36:38Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1273
comments: 0
labels: chore, priority:medium, area:image, effort:medium, semver:patch, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-26T14:51:11.549Z
---

# [Issue 1273]: [Advance pinned nixpkgs rev to drop propagated vulnix exception blocks (openssl, curl, openssh, jq)](https://github.com/vig-os/devkit/issues/1273)

## Context

The pinned nixpkgs rev (`nixos-26.05` @ `34268251cf`, 2026-06-22) predates several security fixes that have since propagated to the channel. Verified online 2026-07-26 during the #1264/#1265 triage (1.4.2 train):

| Package | Pinned | nixos-26.05 HEAD | Clears register block |
|---------|--------|------------------|----------------------|
| openssl | 3.6.2 | **3.6.3** (NixOS/nixpkgs#530964, backport #531387) | 10 CVEs (exp 2026-08-15) |
| curl | 8.20.0 | **8.21.0** | 17 CVEs (exp 2026-08-15) |
| openssh | 10.3p1 | **10.4p1** | CVE-2026-60002 (exp 2026-08-15) |
| jq | 1.8.1 | **1.8.2** | CVE-2026-49839 (exp 2026-08-03) |

Still **not** in the channel (exceptions must stay): unbound 1.25.2 (staging-26.05 only, NixOS/nixpkgs#544610), gawk 5.4.1, podman 5.8.4, libssh2, fzf 0.73.1.

## Task

- [ ] Advance `flake.lock` nixpkgs to current `nixos-26.05` (Renovate `nix` manager / `lockFileMaintenance`, #638 lever)
- [ ] Rebuild image, re-run vulnix locally; re-triage any *new* surface the advance drags in
- [ ] Drop the openssl, curl, openssh CVE-2026-60002, and jq CVE-2026-49839 blocks from `.vulnixignore`
- [ ] Re-check whether unbound 1.25.2 / gawk 5.4.1 / podman 5.8.4 have landed by then; flip those too if so

Deliberately kept out of the 1.4.2 patch train (mass rebuild + a month of channel churn); target the next content release.

Refs: #1264, #1265, #638
