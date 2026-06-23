---
type: issue
state: open
created: 2026-06-23T06:54:15Z
updated: 2026-06-23T06:55:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/639
comments: 0
labels: area:image
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:47.920Z
---

# [Issue 639]: [T4.1 — Publish-cutover to the Nix image (GATED)](https://github.com/vig-os/devcontainer/issues/639)

Tracking: #625



## Context

Flip the published `ghcr.io/vig-os/devcontainer` image to the Nix-built, multi-arch image.
This is the only hard-to-reverse step, so it is gated on the #637 CVE gate + test/image parity and keeps the Debian
`Containerfile` in-tree as a fallback for one release cycle.

## Scope

**In:**
- Publish the Nix multi-arch image.
- Retain the Debian `Containerfile` in-tree as fallback for one release cycle.
- Run **both** nightly scans for one cycle to compare findings.

**Out:**
- Debian removal (#642).

## Go / no-go gate

- T2 green (image + portable tests + multi-arch).
- #637 CVE gate met (no unexcepted HIGH/CRITICAL; overlap diff archived).

**Rollback (no-go / post-cutover regression):** re-point the published `:latest` / release
tags at the last Debian-built digest (retained in-tree and in the registry for this cycle).
Because consumers digest-pin, an in-flight rollback only affects repos that re-resolve `:latest`;
no downstream change is required to recover.

## Tasks

- [ ] Publish the Nix multi-arch image as `:latest` / release tags
- [ ] Keep the Debian build available as fallback for one cycle
- [ ] Run both nightly scans and archive the comparison

## Acceptance criteria

- `ghcr.io/vig-os/devcontainer:latest` is Nix-built and multi-arch.
- Downstream consumers are unchanged.
- Scan comparison archived.

## Dependencies

- **Depends-on:** #636, #637.
- **Blocks:** #640.

## Files

- `.github/workflows/*`
- release docs

## Test notes

- Confirm a downstream repo pulling the new digest comes up unchanged before declaring the
  cutover done.

