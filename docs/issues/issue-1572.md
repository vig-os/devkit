---
type: issue
state: open
created: 2026-08-26T15:26:19Z
updated: 2026-08-26T15:26:19Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1572
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-27T12:42:14.025Z
---

# [Issue 1572]: [guardrails: export the vendored gates as a stable package (consumable without mkProjectShell)](https://github.com/vig-os/devkit/issues/1572)

## Problem

#1488 vendored the guardrails gates as a capability module, and #1492 settled that the module contributes `packages` only (hook entries are scaffold-rendered; committed consumer configs are never overwritten). The wrapping is the valuable half for any consumer: gate runtime deps (bash, jq, ripgrep, gawk, …) resolve from the store instead of PATH, and `checks.guardrails-canary` proves each gate rejects a known-bad fixture.

But the gates derivation is internal: `guardrailsPkg = pkgs.callPackage ./nix/guardrails.nix { }` lives in a `let` and is reachable only through `mkProjectShell`'s `modules = [ "guardrails" ]`. `packages.<system>` exposes only `services` (plus the Linux-only image targets).

That leaves a gap for a consumer that already owns its dev shell and a committed prek/pre-commit config. The module's own compatibility decision anticipates exactly this consumer — names, `GUARDRAILS_*` env vars, and hook ids are preserved verbatim *so existing configs keep working* — yet such a consumer cannot take the wrapped gates through any stable API. The workarounds are:

- adopt `mkProjectShell` wholesale (a shell migration, when only the gate binaries are wanted), or
- import the internal path (`pkgs.callPackage "${devkit}/nix/guardrails.nix" { }`) — works, but it is not contract and can break on any refactor.

## Ask

1. Export the wrapped gates as `packages.<system>.guardrails` (the derivation already exists; this is surfacing, not new packaging).
2. Optionally, make the execution-proof reusable: either expose the canary as a consumer-usable check, or document that `$out/share/guardrails/gates/test-gates.sh` (already shipped) is the supported way for a consumer to assert gate execution in its own flake.

## Why it fits the existing decisions

- It composes with, rather than reopens, #1492: the config file stays consumer-owned; only the binaries' provenance changes.
- It keeps the scaffold optional, matching the module header's stance that hook entries belong to the scaffold side.
- It widens adoption of the hermetic wrapping — the failure it fixes ("hooks resolved from a developer's global profile, worked there, failed in CI") is called out in `nix/guardrails.nix` itself as the motivating incident.
