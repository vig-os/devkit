---
type: issue
state: closed
created: 2026-09-25T16:04:42Z
updated: 2026-09-25T16:55:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1719
comments: 1
labels: chore, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:39.977Z
---

# [Issue 1719]: [[CHORE] Root and mirror CHANGELOG drift in a released section; pin the Unreleased mirror](https://github.com/vig-os/devkit/issues/1719)

### Chore Type

Documentation / Housekeeping

### Description

`CHANGELOG.md` and its scaffold mirror `assets/workspace/.devcontainer/CHANGELOG.md` are meant to be byte-identical (the sync script skip-lists both, so every edit is made twice by hand and reviewed as a pair). They currently differ in two words inside the **released** `## [1.10.0]` section (lines ~1413/1415):

```
< two latent mis-parses in the old `git status --porcelain | awk '{print $2}'`
> two latent misparses in the old `git status --porcelain | awk '{print $2}'`
< loudly on a path containing a comma rather than mis-splitting it
> loudly on a path containing a comma rather than missplitting it
```

The mirror's spellings are the `typos`-corrected forms; the root keeps the hyphenated originals (the root is exempted differently). Introduced by a3989a5c ("sanitize the synced changelog and guard unreleased entries"), which rewrote the mirror's text without the root. Noticed independently by the reviews of #1711 and #1718.

Released entries are not edited by policy, so this is a recorded, accepted drift unless a mechanism is chosen — which is the real question this issue asks.

### Acceptance Criteria

- [ ] Decide: either (a) a one-time reconciliation of the two words is explicitly allowed as a typo-only fix to a released section (both files end identical), or (b) the drift is documented as accepted in the changelog conventions and a test pins that **only** the `## Unreleased` sections must be identical
- [ ] Whatever is chosen, a pytest pin exists so the root and mirror cannot drift again silently in the section the policy covers (`## Unreleased` at minimum)

### Implementation Notes

The pin is a few lines: read both files, slice from `## Unreleased` to the first `## [`, assert equality. Option (a) additionally needs the `typos` exemption story for the two files to agree so the next hook run does not re-open the gap.

### Related Issues

- a3989a5c / #1423-era changelog sanitising; #1689 (changelog gate hardening)

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 04:55 PM_

Closing: the premise is wrong. The two-word difference is a **declared, tested transform**, not drift. `scripts/manifest.toml` (the `CHANGELOG.md` entry, Refs #1534) de-hyphenates `mis-parses` / `mis-splitting` in the generated mirror only, because devcontainer-mode consumers git-track the mirror and lint it against a `.typos.toml` seeded before #1488 added the `mis` allowance (the live failure #1529 recorded). Released source text stays immutable by design.

The pin the issue asks for already exists in a stronger form: `tests/test_transforms.py::TestChangelogMirrorSanitization::test_mirror_is_the_source_plus_the_transforms` asserts whole-file equality modulo the declared transforms, and `test_released_source_text_is_untouched` guards against exactly option (a). The `sync-manifest` hook regenerates the mirror on every commit and `release.yml` re-runs it on the release branch, so nothing can drift silently. Lesson for reviewers: a root/mirror diff is a finding only after checking the manifest's `transforms`.

