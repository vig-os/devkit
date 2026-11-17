---
rfc: ADR-home-environment-modules
date: 2026-07-03
title: Terminal home environment as devkit home-manager modules
status: accepted
authors:
  - Carlos Vigo (c-vigo)
---

# ADR: Team terminal home environment — artifact shape, placement, and policies

**Decision (TL;DR):** Ship the org's terminal-based, agent-friendly *user*
environment (shell, tmux + sesh, editor, git/gh tooling, `~/.claude`
conventions) as **parameterized home-manager modules exported from this repo**
(`homeManagerModules.*`, option namespace `vigos.*`), consumed by (a) the
private NixOS server fleet via home-manager's NixOS module, and (b) personal
machines via standalone home-manager — **not** by the devcontainer image, which
keeps its current lean bootstrap. The modules are a **second product** of this
repo with their own CI matrix (incl. an `aarch64-darwin` build + Cachix push),
doc surface, and API/versioning policy, but they share the repo's `devTools`
SSoT, lockfile, and release train. The only new flake input is `home-manager`:
**no nixvim** (the editor module uses `programs.neovim` + nixpkgs `vimPlugins`)
and **no third-party claude-code flake** (the existing `fastMovers` overlay on
`nixpkgs-unstable` suffices, kept fresh by a scheduled lock bump). Everything is
strictly opt-in: per-module `enable` flags, `lib.mkDefault` on every value, and
an optionality invariant — nothing work-required may depend on the home
environment.

## Problem Statement

The org wants to offer a consistent, terminal-first development environment —
including agentic tooling (Claude Code) — usable by three people across
different surfaces: shared NixOS servers, personal laptops (one NixOS, one
`aarch64-darwin` Mac, one `x86_64-darwin` Mac), and the existing devcontainer.
Users must be free to adopt none, some, or all of it (direnv shell only,
devcontainer only, or the full home environment).

Today the repo delivers the *toolchain* everywhere (image, `mkProjectShell`
dev-shells, thin package-only `homeManagerModules.default` / `nixosModules.default`
from #777), but the *configuration* layer — what makes a machine feel like a
ready workstation — exists only as single-user, hand-maintained personal
configuration outside the org. This repo is the natural home for the shared
carve-out: it is already the org toolchain SSoT, and the pending rename
`devcontainer` → `devkit` (#781) acknowledges the widened scope.

Open questions this ADR settles: artifact shape, repo placement, input policy,
Claude Code sourcing and `~/.claude` management, platform tiers, secrets,
sandboxing posture, and release/versioning for module consumers.

### Current state, enumerated

- **`flake.nix` @ `dev`** already exports `homeManagerModules.default` /
  `nixosModules.default` (#777) — package-only wrappers over `devTools`, no
  configuration, no options beyond `programs.vigos-devtools.enable`.
- **Darwin evaluates but is not built:** darwin systems are in the flake's
  systems list and dev-shells evaluate cleanly, but no CI job builds darwin
  outputs and the Cachix cache holds no darwin closures.
- **Claude Code** ships from the `fastMovers` overlay on `nixpkgs-unstable`
  (`flake.nix`), which now packages Anthropic's official native binary for all
  four arches, bumped near-daily upstream (~1–3 days behind releases; unfree,
  hence not on cache.nixos.org, but the derivation is a trivial fetchurl of
  the official binary — nothing to build). Freshness gaps observed locally are
  lock-pin staleness, not nixpkgs lag.
- **Prior art:** working single-user versions of every intended module exist
  in the maintainer's personal configuration (bash, starship, atuin, tmux,
  sesh standard layout, editor, gh-dash, lazygit, modern-unix CLI set, direnv,
  managed `~/.claude` conventions) and inform the design; they are Linux-shaped
  and unparameterized, so the port is a redesign, not a copy.
- **Consumers:** the org's NixOS servers are configured from a private
  infrastructure repo; two macOS colleagues want to use Nix; the devcontainer
  image is the zero-Nix fallback for everyone.

## Options Considered

### Axis 1 — Artifact shape

**A1 — home-manager modules with custom options (chosen).** An org flake
exporting `homeManagerModules.*`; users/hosts import modules and override via
the module system (`mkDefault` priorities, `mkForce` escape hatch, `extraConfig`
passthroughs).

- **Pros:** The only shape that natively covers the user layer (dotfiles,
  editor, multiplexer, agent config) with a real defaults-plus-overrides
  mechanism, on NixOS, macOS (standalone HM), non-NixOS Linux
  (`targets.genericLinux`), and servers. No vendor. Composes under the existing
  per-project layer (`mkProjectShell` + nix-direnv) without contention.
- **Cons:** Home-manager eval overhead and error opacity for newcomers;
  first-activation collisions with existing dotfiles (documented adoption path
  required).

**A2 — full `homeConfigurations` per user in the org repo.** Zero-boilerplate
onboarding, but couples personal dotfiles to org CI and review. **Rejected as
the primary artifact**; kept only as thin sugar (`homeConfigurations.demo`)
built from the modules.

**A3 — package/profile only (`nix profile install`, wrapper-manager).** Weak
override story, imperative updates, awkward for stateful dotfiles. **Rejected.**

**A4 — Flox / Devbox / devenv as the substrate.** Flox composes environments
well but manages packages, not dotfiles, and adds a per-seat SaaS; Devbox has no
override layering; devenv is per-project by construction (and already rejected
as shell builder by [ADR-nix-devenv-strategy]). **Rejected.**

### Axis 2 — Repo placement

**B1 — this repo (chosen).** The parity argument dominates at this org size:
one `devTools` list, one lockfile, one release train, with the modules as a
declared second product.

- **Pros:** Toolchain parity between shell, image, and home env is enforceable
  by the existing parity-test pattern; module outputs already live here (#777);
  the pending `devkit` rename (#781) already acknowledges the widened scope;
  extraction later is a URL change for consumers.
- **Cons:** Consumers of any output transitively lock all inputs; public repo
  hosts opinionated environment defaults. Both mitigated by the input policy
  (Axis 3) and by everything being opt-in, generic, and parameterized —
  org-private values (identities, workspace docs, secrets) never enter this
  repo.

**B2 — separate env repo.** Cleaner consumer lock in the general case, but at 3
users it duplicates the tool list or creates bidirectional input plumbing, and
its main motivation (heavy inputs) is removed by Axis 3. **Rejected; revisit if
input bloat becomes measurable.**

### Axis 3 — Flake input policy

**C1 — `home-manager` as the only new input (chosen).** The editor module uses
plain `programs.neovim` with nixpkgs `vimPlugins` (incl. `claudecode-nvim`,
packaged in both 26.05 and unstable — beware the distinct `claude-code-nvim`,
a different upstream). A richer nixvim-based editor remains a personal-config
concern; if colleagues want it later it becomes its own small flake.

- **Pros:** Downstream `mkProjectShell` consumers lock one moderate extra input
  instead of nixvim's large graph; no nixpkgs-branch coupling beyond what exists.
- **Cons:** Less expressive editor module than nixvim. Accepted trade.

**C2 — third-party claude-code flake (sadjow/claude-code-nix or
ryoppippi/nix-claude-code), auto-bumped.** **Rejected.** nixpkgs-unstable now
ships the same official native binary for all four arches within ~1–3 days as
a trivial fetchurl (unfree, so not on cache.nixos.org — but there is nothing
to build); the third-party inputs add a single-maintainer
supply-chain dependency plus an extra Cachix trust root for negligible freshness
gain. The org keeps the existing `fastMovers` overlay and adds a **scheduled
`nix flake update nixpkgs-unstable`** (full CI as merge gate) so the pin never
goes stale. Reconsider only if <24 h latency ever becomes a hard requirement.

### Axis 4 — Devcontainer image integration

**D1 — leave the image alone (chosen).** The image keeps its current baked
`/root/.bashrc` + aliases.

- **Rationale:** HM activation cannot run inside `dockerTools` builds
  (home-manager#5258 class: activation needs a live store/profile machinery);
  deferring activation to `onCreateCommand` adds a failure-prone startup step
  (opposite of #718), the closure grows against documented image-size and
  CVE-gate discipline, HM's bash module collides with the baked `.bashrc`, and
  baking an editor config reverses the deliberate nvim isolation (#723). The
  optionality invariant already guarantees the container never *needs* the home
  env.
- **Reconsider if** container ergonomics demonstrably hurt; then evaluate an
  explicitly image-safe subset (shell/tmux only), after #639/#642.

### Axis 5 — `~/.claude` management policy

Verified against Claude Code behavior (native binary, npm deprecated; sandbox
init fails on read-only store symlinks of `settings.json` —
anthropics/claude-code#52525; atomic writes fail through multi-level symlinks —
#15786):

- **Never managed:** `~/.claude.json`, `settings.local.json` (mutable runtime
  state: OAuth, MCP, permission grants). No symlinks of any kind — store or
  out-of-store — anywhere under `~/.claude/`.
- **Seeded, then user-owned:** `settings.json` via `home.activation`
  copy-if-absent — a declarative default that Claude Code may freely rewrite.
  Seed updates never touch an existing file; changes are announced in the
  changelog, and re-seeding means deleting the file and re-activating.
- **Managed (copy, not symlink):** hooks and an org CLAUDE.md *fragment*
  (e.g. `~/.claude/vigos.md`), copied by `home.activation` and
  checksum-overwritten on org updates with a `.bak` of local edits.
  `mkOutOfStoreSymlink` is unusable for shipped modules (it requires a path
  outside the consumer's store), and the top-level `~/.claude/CLAUDE.md`
  stays user-owned because Claude Code itself writes to it (memory feature) —
  seeding adds a single `@vigos.md` import line to it instead.
- **Org defaults never pre-authorize:** no `defaultMode = "auto"`, no
  permission-prompt skipping in shipped defaults (personal configs may add
  them). Auto-update disabled via `DISABLE_AUTOUPDATER=1`, set by the home
  modules through `home.sessionVariables` (not the user-editable seeded
  settings.json). Amended by [#2076](https://github.com/vig-os/devkit/issues/2076):
  only when `vigos.packages.agentCli.enable` installs devkit's pinned CLI,
  which is now opt-in; extending it to the dev-shell/image is a separate follow-up
  chore outside this ADR.
- **No home-level skills:** repos remain the skills SSoT (the existing
  `assets/workspace/.claude/` scaffold); the home layer carries only CLAUDE.md,
  seeded settings, and hooks.

### Axis 6 — CLAUDE.md hierarchy

Shipped as **templates + guidelines**, not managed files: org-parent, workspace,
and user-level CLAUDE.md examples mirroring the root-to-cwd cascade, with the
directory-layout convention (`~/<workspace-root>/<workspace>/<repo>`) documented
as the assumption that makes the workspace layer work. An optional,
**off-by-default** HM option can symlink-manage a user-declared path→file
attrset (default empty — the seven-symlink personal pattern is not portable
as-is).

## Platform & consumer policy

| Consumer | Mode | Tier |
|----------|------|------|
| NixOS servers (private infra repo) | HM as NixOS module, `home-manager.users.<name>`, per-user opt-in | First-class |
| NixOS / Linux laptops | standalone HM (or NixOS module in personal flake) | First-class |
| `aarch64-darwin` | standalone HM; CI builds + Cachix push **before first onboarding** | First-class |
| `x86_64-darwin` | standalone HM | **Best-effort**: eval-checked only, never CI-built or cached; supported fallback is the amd64 devcontainer image; ends at nixpkgs 26.05 EOL (2026-12-31, last x86_64-darwin release) |
| Devcontainer image | not integrated (Axis 4) | n/a |

- **One HM mode per user per host:** centrally-managed (NixOS module) and
  standalone HM must not be mixed for the same user on the same machine (shared
  activation state clobbers); different users on one host may differ.
- **Shell:** modules support **bash and zsh** (macOS default) via the standard
  `enable{Bash,Zsh}Integration` toggles; no login-shell mandate.
- **nix-darwin:** out of scope v1 (standalone HM suffices for user-level
  config). Trigger to revisit: a Mac needs system-level management.
- **Credentials (resident, scoped):** persistent remote sessions (tmux/sesh
  surviving SSH disconnects) require resident per-user credentials on servers;
  SSH agent forwarding is rejected (sockets die with the connection and are
  hijackable on shared hosts). Devkit standardizes the *interface* only:
  per-secret files under `~/.config/vigos/secrets/<NAME>` (mode 0600), with an
  opt-in `vigos.shell.secretsEnv` hook exporting each as an environment
  variable (names restricted to `[A-Z_][A-Z0-9_]*`, trailing newline
  stripped, sourced idempotently from both profile and rc files; systemd user
  services and non-interactive SSH commands are out of scope v1).
  Deployment is out of scope — sops-nix is the natural backing on NixOS
  servers; laptops hand-place files or keep OS-native flows (Keychain
  `/login`, `gh auth login`). Tools must keep working with interactive auth
  for users who don't adopt the convention (optionality invariant). The same
  canonical location is what the devcontainer mounts/env-files for
  agent-token forwarding (#546).
- **Credential hygiene:** scoped and revocable only — fine-grained, expiring
  GitHub PATs (never classic tokens); Claude long-lived OAuth token from
  `claude setup-token` (console-revocable); Cachix is **not** a per-user
  credential (pulls are anonymous, pushes are CI/system-level). **SSH keys —
  authentication and signing alike — are minted per user × host and never
  copied**; each is registered with the forge individually, so a commit
  signature identifies the machine it was made on and a compromise revokes
  one host, not an identity. Threat-model note: any same-uid process
  (including an agent) can read resident secrets — credential scoping and the
  container working agreement are the mitigations, not the storage location.
  Trigger to revisit: a shared service token must reach a laptop → adopt
  sops-nix's HM module on darwin.
- **Sandboxing (working agreement, not a control):** interactive,
  permission-prompted agent use is fine everywhere; autonomous /
  `--dangerously-skip-permissions` runs happen **inside the container** (podman,
  incl. on shared servers). This is enforceable only socially today — the `cld`
  skip-permissions alias exists only inside the image (though the worktree
  pipeline recipes invoke the flag directly wherever they run) and org
  defaults pre-authorize nothing — and is therefore documented as a working
  agreement,
  with a bwrap wrapper module as tracked future enforcement. It must not be
  represented as a security boundary.

## Optionality invariant

Adoption tiers are strictly additive, and **nothing required for work may
depend on the home environment**: project CI, dev-shells, the devcontainer,
pre-commit, and all `just` verbs must function for a user at tier "none".

```
none  →  direnv dev-shell  →  devcontainer  →  home environment
```

## API & release policy

- **Namespace:** `vigos.*` (org-branded, rename-proof), per-concern submodules
  (`vigos.shell`, `vigos.multiplexer`, `vigos.git`, `vigos.claude`, …), every
  module `enable`-gated, every scalar setting written with `lib.mkDefault`,
  `extraConfig` passthroughs on managed programs. Modules *configure*;
  packages ship only via `homeManagerModules.packages` (no module duplicates
  the `devTools` list), and modules resolve packages from devkit's own locked
  nixpkgs + `overlays.default` — the #777 module's documented constraint (HM
  under `useGlobalPkgs` cannot inject consumer overlays) — so tool versions
  match the dev-shell and image per system. `programs.vigos-devtools`
  migrates via `mkRenamedOptionModule`; the package-only module becomes
  `homeManagerModules.packages`, and `homeManagerModules.default` becomes the
  umbrella importing all `vigos.*` modules (each disabled by default), so
  existing #777 imports keep working unchanged. Both `homeManagerModules.*`
  and the newer-convention `homeModules.*` aliases are exported.
- **Versioning:** modules ride the existing release train — consumers pin
  `github:vig-os/devcontainer/<tag>` (post-#781: `devkit`) and bump
  deliberately. No separate release cycle; no `main`/`dev` tracking is
  documented for consumers. The shipped workspace scaffold currently floats
  untagged on the default branch — aligning it with this policy (pin, or an
  explicitly documented float) is part of the rollout. One exception: the
  maintainer's personal configuration tracks `dev` during the dogfood phase
  as the pre-release canary; the pin-tags policy applies to all other
  consumers, and to it once the first module-bearing tag ships.
- **Deprecation:** option renames keep a `mkRenamedOptionModule` shim for one
  release and get a changelog entry. `CHANGELOG.md` gains a *modules*
  subcategory under the standard Keep-a-Changelog headings, since options are a
  consumer-facing API.
- **CI:** flake checks build a homeConfigurations matrix — `minimal` (only
  `vigos.shell`) and `full` (every module) for a synthetic user `ci`
  (`/home/ci`; `/Users/ci` on darwin; pinned `stateVersion`) across
  {x86_64-linux, aarch64-linux, aarch64-darwin}. Checks are per-system: the
  x86_64-linux legs join the landed Tier-0 gate (#778/#779, via PR #791),
  aarch64-linux legs run on arm runners, and the darwin legs build only in
  the dedicated `aarch64-darwin` job that also pushes closures to Cachix. GitHub's `macos-*-intel` runners exist
  (~until fall 2027) but are deliberately unused, consistent with the
  best-effort Intel tier.

## Migration & dogfooding

The maintainer's personal configuration is the first consumer: each wave lands
in devkit, is then imported there in place of the equivalent private config
(plus personal parameters), with a **generation-diff acceptance bar** —
`nvd diff` shows no package changes, *and* a recursive diff of the old vs new
generations' `home-files` trees shows only differences enumerated in the
wave's sub-issue (the expected-diff allowlist) — before the private copy is
deleted:

1. **Wave 1 — generic:** bash/zsh, starship, atuin, direnv, tmux, modern-unix
   (platform-guarded: `wl-clipboard` etc. behind `stdenv.isLinux`), git/gh.
2. **Wave 2 — claude:** the `vigos.claude` module under the Axis-5 policy,
   plus agent runtime dependencies (node/uv for MCP servers); the devcontainer
   consumes the canonical secrets directory (env-file/mount — compose
   scaffolding only, the image itself stays untouched per Axis 4) as the slim
   token-forwarding path #546 asks for.
3. **Wave 3 — parameterization-heavy:** sesh (project list becomes an option
   API), gh-dash (filters/paths become options), editor (`programs.neovim`,
   no nixvim).

Server-side consumption is the private infrastructure repo's change, out of
scope here beyond keeping the modules cleanly importable.

## Impact

- **Beneficiaries:** server users get the environment with the machine; the
  arm-Mac colleague gets a supported laptop path; the container and dev-shell
  products are untouched (input growth limited to `home-manager`).
- **Risks:** bus factor of one Nix expert — mitigated by small waves, the
  rollback one-pager (HM generations / `nixos-rebuild --rollback` / image-tag
  pin), copy-if-absent for fragile files, and the container as the always-on
  fallback. Laptop-tier adoption may stay low; the same modules serving the
  server fleet keep the work useful regardless.
- **Docs:** a module-consumer doc set (bootstrap incl. the macOS
  `trusted-users`/Cachix trap, override cookbook, rollback, uninstall,
  credential-hygiene one-pager incl. rotation/offboarding runbook) is a
  deliverable, not an afterthought; onboarding acceptance test = a colleague
  reaches `home-manager switch` on the arm Mac with zero live help.

## Decision & Recommendation

Adopt A1 + B1 + C1 + D1 with the Axis-5/6 policies, platform table, optionality
invariant, API/release policy, and wave-based migration above.

### Reconsider if

- Consumer lock bloat or eval time becomes measurable pain → extract the module
  library to its own repo (URL change for consumers).
- Claude Code freshness (<24 h) becomes a hard requirement → dedicated
  claude-code input (prefer sadjow/claude-code-nix), still auto-update-disabled.
- Container ergonomics demonstrably suffer → evaluate an image-safe module
  subset (shell/tmux only), after #639/#642.
- Colleagues ask for the full nixvim experience → separate small editor flake,
  not a devkit input.
- A shared secret must reach a laptop → sops-nix HM module on darwin.
- Autonomous agent use on hosts grows → promote the bwrap wrapper from backlog
  to track.

## References

- Sibling ADRs: [ADR-nix-devenv-strategy](ADR-nix-devenv-strategy.md),
  [ADR-uv2nix-pyproject-nix](ADR-uv2nix-pyproject-nix.md).
- In-repo: `flake.nix` (`devTools`, `fastMovers`, `mkProjectShell`,
  `homeManagerModules`/`nixosModules` @ #777), `docs/NIX.md`,
  `assets/workspace/`, issues #814 (epic), #545, #546, #625, #639, #642, #718, #723, #777,
  #779 (landed via PR #791), #781, #795.
- Upstream: nix-community/home-manager (NixOS-module per-user opt-in;
  activation-in-OCI limitation #5258; 25.11 profile-management change),
  nixpkgs `claude-code` (native binary, all four arches),
  `vimPlugins.claudecode-nvim`, anthropics/claude-code#52525 / #15786
  (symlinked-settings breakage), NixOS 26.05 release notes (last
  x86_64-darwin release; EOL 2026-12-31), GitHub runner images
  (macos-latest = arm64; `macos-15-intel`/`macos-26-intel` until ~fall 2027).
