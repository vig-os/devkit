# ADR: Manifest-aware managed documentation

Status: accepted for [#1910](https://github.com/vig-os/devkit/issues/1910).

`SECURITY.md` and `docs/COMMIT_MESSAGE_STANDARD.md` remain managed files.
Render their configuration-dependent text in `assets/init-workspace.sh` after
copying the canonical templates, following the existing workflow and hook
rendering architecture. The default scaffold remains byte-identical.

The security policy omits scanning claims and the Scorecard findings section
when `scanning` is disabled. The commit standard uses the already resolved
`RESOLVED_REFS_OPTIONAL_TYPES`, including explicit-list precedence over
`DEVKIT_REFS_POLICY`, rather than duplicating manifest resolution.

Scaffold Drift reuses this renderer, so a configured consumer can pass without
editing managed documents. Preserving these files or excluding them from drift
would strand stale policies on upgrades; neither exception is introduced.
Regression tests cross scanning enablement with default, required, optional,
and explicit Refs exemptions, and run the real drift script against the inox
manifest with the Nix source lookup stubbed to the checkout.
