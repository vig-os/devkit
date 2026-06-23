---
type: issue
state: closed
created: 2026-01-23T15:32:05Z
updated: 2026-06-23T06:56:50Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/27
comments: 2
labels: feature, priority:low, area:image, effort:large, semver:minor
assignees: gerchowl, c-vigo
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:59.789Z
---

# [Issue 27]: [Adopt Nix/devenv for reproducible, auditable dependency management](https://github.com/vig-os/devcontainer/issues/27)

## Summary

Replace the current ad-hoc tooling installation (apt + curl | bash + manual version tracking) with Nix/devenv for declarative, reproducible, and cryptographically verified dependency management. This addresses regulatory requirements for medical device software (IEC 62304, FDA cybersecurity guidance) while eliminating the manual synchronization between `Containerfile` and `EXPECTED_VERSIONS` in tests.

**Key benefits:**
- Single source of truth for all tool versions (`flake.nix` + `flake.lock`)
- Cryptographic hash verification of all dependencies (supply chain security)
- Air-gapped/offline rebuild capability for regulatory compliance
- Automatic SBOM generation from dependency graph
- Reproducible builds years after initial release

---

## Current Pain Points

### 1. Version tracking is manual and fragmented

Versions are scattered across:
- `Containerfile` (implicit "latest" for gh, just, uv via curl)
- `tests/test_image.py` `EXPECTED_VERSIONS` dict (manually maintained)

Updates are reactive—tests fail after rebuild, then we update the test file.

### 2. No reproducibility guarantee

```dockerfile
# Current: fetches "latest" at build time
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
```

Building the same Containerfile 3 months later produces different results.

### 3. Supply chain vulnerabilities

- `curl | bash` patterns trust remote scripts
- apt packages trust Debian mirrors
- No cryptographic verification of most downloads (gh and uv have manual checksum verification, but just does not)

### 4. Regulatory gaps

- No built-in SBOM generation
- Difficult to prove "rebuild from source" capability
- No formal approval workflow for dependency updates

---

## Proposed Solution: Nix/devenv

### What changes

| Current | Proposed |
|---------|----------|
| `apt-get install git curl` | `packages = [ pkgs.git pkgs.curl ]` |
| `curl \| bash` for tools | Nix packages with pinned hashes |
| `EXPECTED_VERSIONS` in tests | Derived from Nix metadata (or eliminated) |
| Implicit "latest" versions | Explicit pins in `flake.lock` |

### Example `devenv.nix`

```nix
{ pkgs, ... }:
{
  packages = [
    pkgs.git
    pkgs.curl
    pkgs.gh
    pkgs.just
    pkgs.uv
    pkgs.pre-commit
    pkgs.ruff
  ];

  languages.python = {
    enable = true;
    version = "3.12";
  };
}
```

### `flake.lock` provides cryptographic pins

```json
{
  "nodes": {
    "nixpkgs": {
      "locked": {
        "narHash": "sha256-abc123...",
        "rev": "def456..."
      }
    }
  }
}
```

---

## Regulatory Benefits (IEC 62304 / FDA)

### 1. Air-gapped/offline builds

```bash
# Archive all sources for offline rebuild
nix flake archive --json > archive-manifest.json

# Export binary cache
nix copy --to file:///path/to/offline-cache .#devcontainer
```

Enables "rebuild without internet" for controlled manufacturing environments.

### 2. Supply chain protection

Every dependency is content-addressed:
- Source tarballs verified by SHA256
- Git commits verified by tree hash
- Build outputs verified by content hash

**Hash mismatch = build failure** (detects tampering automatically)

### 3. SBOM generation

```bash
nix derivation show .#devcontainer > sbom.json
```

Complete dependency tree with versions, hashes, and sources.

### 4. Change control

```bash
# Diff between releases shows exactly what changed
diff release-1.0/flake.lock release-1.1/flake.lock
```

`flake.lock` becomes a controlled document for regulatory submissions.

---

## Update Workflow Comparison

| Update type | Current | With Nix |
|-------------|---------|----------|
| **Patch** | Automatic on rebuild (reactive) | `nix flake update` (proactive, controlled) |
| **Minor** | Automatic, may surprise | Explicit, reviewed before merge |
| **Major** | Manual Containerfile edit + test update | Change one line in `devenv.nix` |
| **Rollback** | Rebuild from git history, hope repos unchanged | `git checkout flake.lock && nix build` (identical) |

### Security updates

- Stable nixpkgs channels backport security fixes
- Automated PRs via Renovate/Dependabot for `flake.lock` updates
- Weekly update cadence recommended

---

## Trade-offs

### Costs

- **Learning curve**: Team needs Nix familiarity
- **Image size**: ~200-400 MB larger (Nix store overhead)
- **Build time**: Initial builds slower (Nix evaluation)

### Mitigations

- Start with hybrid approach (Debian base + Nix for tools)
- Use binary cache to speed up builds
- Incremental adoption possible

---

## Implementation Steps

- [ ] Evaluate devenv vs pure flake approach
- [ ] Create `flake.nix` with current tool set
- [ ] Verify all tools available in nixpkgs (gh, just, uv, pre-commit, ruff)
- [ ] Set up binary cache (Cachix or self-hosted)
- [ ] Implement offline archive workflow
- [ ] Update tests to derive expected versions from Nix (or remove version checks)
- [ ] Document regulatory workflows (SBOM generation, approval process)
- [ ] Update CI pipeline

---

## References

- [devenv documentation](https://devenv.sh/)
- [Nix flakes](https://nixos.wiki/wiki/Flakes)
- [Nix for reproducible builds](https://nixos.org/guides/reproducible-builds.html)
- [FDA Cybersecurity Guidance](https://www.fda.gov/medical-devices/digital-health-center-excellence/cybersecurity)
- [IEC 62304 - Medical device software lifecycle](https://www.iso.org/standard/38421.html)

---

cc @c-vigo for discussion
---

# [Comment #1]() by [gerchowl]()

_Posted on February 28, 2026 at 09:44 PM_

I've been prototyping the Nix approach in a standalone repo: [gerchowl/devbase](https://github.com/gerchowl/devbase) (private, ask for access).

What's implemented so far:
- Pure Nix container image via `flake.nix` — all tools from nixpkgs, pinned via `flake.lock`
- `devenv.nix` for host-side dev shell (just, podman, bats, linters) with direnv auto-activation
- Entrypoint with secrets management (age-encrypted API keys, SSH keys, gh token, Claude credentials)
- `scripts/deploy.sh` for scaffolding child projects (`FROM devbase:latest`)
- `nix run github:gerchowl/devbase -- ./my-project` for bootstrapping from anywhere
- bats + container-structure-test suite
- CI workflows (build, test, scheduled rebuild)

This is a prototype/sandbox — not a migration plan. Serves as a reference for what the Nix layer could look like when we tackle this in devc.

---

# [Comment #2]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Superseded by the Nix migration epic #625 and its sub-issues. #625 is the decided execution of this proposal: full flake-as-SSoT (#631) + a `buildLayeredImage` devcontainer image (#634), with the IEC 62304 / SBOM / air-gapped framing preserved in #637. Closing in favour of the epic.

