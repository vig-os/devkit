---
rfc: ADR-manifest-aware-managed-docs
date: 2026-10-26
title: Manifest-aware managed documentation
status: accepted
authors:
- gerchowl
---

# ADR: Manifest-aware managed documentation

Status: accepted for [#1910](https://github.com/vig-os/devkit/issues/1910).

`SECURITY.md` and `docs/COMMIT_MESSAGE_STANDARD.md` remain managed files.
Render their configuration-dependent text in `assets/init-workspace.sh` after
copying the canonical templates, following the existing workflow and hook
rendering architecture. The default scaffold remains byte-identical.

The security policy omits scanning claims and the Scorecard findings section
when `scanning` is disabled, and omits Renovate monitoring claims when
`renovate` is disabled. The commit standard uses the already resolved
`RESOLVED_REFS_OPTIONAL_TYPES`, including explicit-list precedence over
`DEVKIT_REFS_POLICY`, rather than duplicating manifest resolution.

Scaffold Drift reuses this renderer, so a configured consumer can pass without
editing managed documents. Preserving these files or excluding them from drift
would strand stale policies on upgrades; neither exception is introduced.
`test_managed_docs_follow_manifest` is the regression matrix: it crosses
scanning and Renovate enablement with default, required, optional, custom-type,
and explicit Refs exemptions, and fails on `origin/dev`.
The separate inox drift test runs the real drift script with Nix source lookup
stubbed to the checkout. It verifies clean-render/hand-edit drift behavior;
it also passes on `origin/dev`, so it is integration coverage rather than
a regression test for the document wording.

## Alternatives considered

- **Preserve-class documents:** rejected because consumer copies would retain
  stale policies on upgrades instead of receiving corrected managed content.
- **Exclude these documents from Scaffold Drift:** rejected because it would
  hide hand edits and let published policy diverge from the rendered manifest.
- **Honor `DEVKIT_UPGRADE_EXCLUDE` in the drift job:** rejected because an
  upgrade selection knob would then weaken drift verification and still leave
  incorrect default documents for consumers who do not set it.

## Feature audit

The security policy names scanning and Renovate as optional practices; both
are rendered independently. Dependency review remains in core CI, and the
remaining practices do not depend on optional feature groups. The commit
standard’s Refs wording follows the resolved exemption list and retains the
issue-less branch rule even when the skills feature is disabled: branch guards
and CI enforce that rule independently of the skill documents.
