---
type: issue
state: open
created: 2026-09-02T05:37:54Z
updated: 2026-09-02T05:37:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1599
comments: 0
labels: chore, priority:low, area:ci, area:workspace, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-09-02T07:01:33.209Z
---

# [Issue 1599]: [[CHORE] devkit-upgrade.yml installs Nix without accept-flake-config — consumer flake substituters ignored](https://github.com/vig-os/devkit/issues/1599)

### Chore Type

CI / Build change

### Description

The scaffolded `devkit-upgrade.yml` installs Nix with only
`experimental-features = nix-command flakes`:

```yaml
# assets/workspace/.github/workflows/devkit-upgrade.yml:213-218
- name: Install Nix
  uses: cachix/install-nix-action@13d8dd58da0234aa297dedd986986ccb8e7f3e24  # v31.11.1
  with:
    extra_nix_config: |
      experimental-features = nix-command flakes
```

Its sibling in the same scaffold payload does not:

```yaml
# assets/workspace/.github/actions/setup-devkit-toolchain/action.yml:116-120
extra_nix_config: |
  experimental-features = nix-command flakes
  accept-flake-config = true
  extra-substituters = https://vig-os.cachix.org
  extra-trusted-public-keys = vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=
```

Consequence: in a `direnv`-mode consumer whose `flake.nix` declares a
`nixConfig` block, every scheduled upgrade run prints

```
warning: ignoring untrusted flake configuration setting 'extra-substituters'.
Pass '--accept-flake-config' to trust it
warning: ignoring untrusted flake configuration setting 'extra-trusted-public-keys'.
Pass '--accept-flake-config' to trust it
```

twice — once under `Run the devkit upgrade (install.sh --force)` (the
`nix flake update vigos` bump) and once under `Commit the upgrade in the project
shell` (the `nix develop -c git commit`). The vig-os substituter is unavailable
in both, so the dev-shell realisation resolves against `cache.nixos.org` alone.

The same two workflow steps are the only Nix consumers in that job, and the
`nix develop` one is where the whole job's wall-clock sits.

### Calibration (do not oversell this)

An observed scheduled run in a `direnv` consumer spent 4m39s of a 5m38s job in
the commit step, substituting 847 paths and running 72 local builds. **Most of
that would not have been recovered by this fix**: the upgrade step had just
advanced the consumer's `nixpkgs` pin, so the resulting dev-shell closure was
new and no cache held it. `vig-os.cachix.org` is populated by `nix-cachix.yml`
from *devkit's own* dev-shell at *devkit's* nixpkgs pin, which only partly
overlaps a consumer's.

So this is a **consistency/correctness fix that removes two per-run warnings and
restores the substituter the consumer's own flake asked for** — not a
performance fix. Filing it at `priority:low` for that reason.

### Not a regression of #773

\#773 removed `accept-flake-config = true` from the **image's baked
`/etc/nix/nix.conf`**, where it would make any in-container
`nix run github:attacker/flake` silently trust a foreign flake's substituters.
That constraint is unchanged and `tests/test_image.py::test_nix_conf_does_not_accept_flake_config`
still guards it.

This is the other case: a per-runner installer setting, in a job that evaluates
**the consumer's own repo flake** and nothing else — the identical posture
`setup-devkit-toolchain` already ships.

### Acceptance Criteria

- [ ] `assets/workspace/.github/workflows/devkit-upgrade.yml`'s `Install Nix`
      step carries the same four `extra_nix_config` settings as
      `setup-devkit-toolchain`'s `Install Nix (upstream CppNix)` step
- [ ] A test keeps the two in lockstep, in the spirit of
      `tests/test_setup_toolchain_env.py::test_install_and_host_paths_carry_identical_settings`
- [ ] `tests/test_image.py::test_nix_conf_does_not_accept_flake_config` still
      passes (the baked image config is untouched)
- [ ] Both `warning: ignoring untrusted flake configuration setting` lines are
      gone from a consumer's next upgrade run

### Implementation Notes

Three added lines plus a test. Note the settings now live in three scaffold
places (`setup-devkit-toolchain` install path, its host-Nix `NIX_CONFIG` path,
and `devkit-upgrade.yml`); prefer extending the existing lockstep test over
adding a third independent expectation.

Consumers pick this up on their next adoption PR — the workflow is
devkit-managed, so no consumer-side edit is wanted or durable.

