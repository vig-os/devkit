---
type: issue
state: open
created: 2026-10-05T18:36:05Z
updated: 2026-10-05T18:36:05Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1832
comments: 0
labels: feature, priority:low, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: 1833
children: none
synced: 2026-10-06T08:50:57.024Z
---

# [Issue 1832]: [direnv flake template: package consumers inherit devkit's whole input tree via nixpkgs.follows = vigos/nixpkgs](https://github.com/vig-os/devkit/issues/1832)

## Problem
The scaffolded direnv `flake.nix` sets `nixpkgs.follows = "vigos/nixpkgs"` (and `flake-utils.follows = "vigos/flake-utils"`). That is right for the dev shell. But when the project itself exposes `packages` and another flake consumes it as an input to get one binary, the consumer's lock inherits devkit's entire input tree: home-manager (two channels), crane, fenix, git-hooks, process-compose-flake, services-flake, treefmt-nix, nixpkgs-unstable, and so on. None of it is needed to build the package.

## Impact
- Lock churn and download/eval cost for every downstream consumer.
- Downstream maintainers must chain `inputs.<project>.inputs.vigos.inputs.nixpkgs.follows = …` to dedupe nixpkgs, and still carry the rest.

## Proposed
Pick one, or both:
- **Template change:** declare a top-level `nixpkgs` input and have `vigos` follow it (`vigos.inputs.nixpkgs.follows = "nixpkgs"`), instead of the reverse. Packages then build from the project's own nixpkgs, and a consumer's `follows` works naturally.
- **Docs:** add a "projects that ship packages" section. Build `packages.*` from plain `nixpkgs.legacyPackages` (not the devkit-overlaid `pkgs`), and give the recommended consumer `follows` stanza.

Caveat: devkit pins its nixpkgs deliberately (dev-shell/image parity). The template change would need a guard that the followed revision still satisfies devkit, or a scope limited to the package outputs.

