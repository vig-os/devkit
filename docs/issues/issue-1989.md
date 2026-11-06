---
type: issue
state: open
created: 2026-11-03T00:19:13Z
updated: 2026-11-03T00:19:13Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1989
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T09:20:22.211Z
---

# [Issue 1989]: [flake-bump: pin parsing follow-ups from the #1856 review (extra query params, refs/heads test, CI wording, v-pin at target)](https://github.com/vig-os/devkit/issues/1989)

Follow-ups from the reviews of #1988 (#1856). None blocks the merge.

1. **Lockstep pin with extra query params gets no warning.** `?ref=1.2.2&dir=sub` (or `?dir=sub&ref=1.2.2`) is read with the whole query tail as the ref. It is skipped as "not in lockstep", with no incomplete-upgrade warning, even though the scaffold moved. The same parsing is used in the main path, in `warn_incomplete_pin_upgrade` and in the scaffold ci.yml pin gate. Parse `ref=` as one query param.
2. **Untested branch-ref guard.** A mutant that strips `refs/heads/` in `normalize_release_ref` survives the whole test suite. Add `?ref=refs/heads/X` to the bats "non-release pin is left alone" loop.
3. **Installer warning overstates CI.** The installer always says "CI will reject the pin/version mismatch". The ci.yml gate only warns for qualified refs (`refs/tags/X`), and the same applies when the new DEVKIT_VERSION is not a release.
4. **A `v` pin already at the target** (`?ref=v1.2.3` upgrading to 1.2.3) is skipped as "not in lockstep" and keeps a nonexistent tag, while knob `true` rewrites it. Say "already at target", or canonicalize it.
5. **Not verified with real nix:** whether the path form `github:vig-os/devkit/refs/tags/X` resolves.

Refs: #1856
