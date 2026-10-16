---
type: issue
state: open
created: 2026-10-15T21:40:43Z
updated: 2026-10-15T21:40:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1897
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-16T06:58:51.341Z
---

# [Issue 1897]: [spike: CI without third-party actions — Nix-provided checkout/tooling as a devkit convention (hard spike)](https://github.com/vig-os/devkit/issues/1897)

## Proposal: hard spike
Run this as a `/spike`: file it, take varied expert reviews (CI security, Nix/devkit maintainer, performance, DX), decide, and only then build.

## Motivation
On 2026-10-15, ksb ARC runners (self-hosted k3s, one shared egress IP) hit HTTP 429 from codeload.github.com: `actions/checkout` was downloaded 123 times in 80 minutes, because ephemeral runner pods re-download every action tarball for every job. Six jobs failed at "Set up job". exo-pet/exo-fleet#947 adds a local action-archive cache, which fixes the symptom on ksb. The underlying question is broader: **do our workflows need third-party JS actions at all?**

Today:
- Container images are cached by containerd.
- Nix dependencies come from the local attic or the shared store.
- Third-party actions are the only per-job download from GitHub. They are also an unpinned supply-chain surface (tags move, transitive `uses:`), and they need node in the runner.

## Hypothesis
A devkit convention where CI uses **Nix-provided tooling only**:
- checkout via plain `git` (or a tiny devkit-owned composite action with no JS) using the job token;
- `nix develop -c …` for every tool instead of `setup-*` actions;
- caching via attic/cachix through Nix config, not `actions/cache`.

This would make jobs faster to set up, reproducible, free of action downloads, and smaller in attack surface. It would also be portable across GitHub-hosted runners, ksb ARC, and future runners.

## Questions the spike must answer
1. Which actions do our ~N repos (vig-os, exo-pet, MorePET, exoma-ch, gerchowl) actually use? Inventory them all via the API and classify each as replaceable by Nix / devkit-owned / unavoidable (e.g. `upload-artifact`, `github-script`, OIDC, App token).
2. Checkout without `actions/checkout`: auth (`GITHUB_TOKEN` / App token), LFS, submodules, sparse checkout, fetch depth, PR merge refs, `persist-credentials` semantics. Measure setup-time deltas on ksb and GitHub-hosted runners.
3. Unavoidable actions: vendor them into devkit as pinned, SHA-verified composite or Nix-packaged equivalents? Or keep them, served from the #947 cache?
4. Security: does removing JS actions reduce or shift risk (token handling in shell, script injection via `${{ }}`)? Guardrails such as actionlint, zizmor, and `persist-credentials: false` defaults.
5. Migration path: a devkit reusable workflow and template, per-repo opt-in, and a lint that flags third-party `uses:`.

## Deliverables
- An ADR in devkit with the decision and its trade-offs.
- If adopted: a prototype reusable workflow plus a template, with measured setup-time numbers (ksb ARC vs GitHub-hosted, before and after).

## Pitfalls
- Re-implementing `actions/checkout` badly: credentials left in `.git/config`, wrong PR refs, and submodule auth.
- GitHub-only features that are actions by design: artifacts, caches API, OIDC token exchange, check-run annotations.
- Breaking contributors' expectations and Dependabot or Renovate action-update flows.
- Larger Nix closures on cold GitHub-hosted runners, which could make them slower unless the binary cache is reachable.

Refs: exo-pet/exo-fleet#946/#947 (ARC action-archive cache), #911 (CI trust tiers).

