---
type: issue
state: open
created: 2026-11-11T17:59:10Z
updated: 2026-11-11T17:59:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2074
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-12T09:37:22.667Z
---

# [Issue 2074]: [validate-branch-name rejects devkit's own suggested upgrade-branch name (dots in slug)](https://github.com/vig-os/devkit/issues/2074)

## Bug

`validate-branch-name` (vig-utils, bundled in 1.19.0) only accepts `[a-z0-9-]` in the branch slug after the
type, both for the issue-numbered `<type>/<issue>-<summary>` form and the issue-less `<type>/<summary>` form. A
dot anywhere in the slug fails validation:

```
$ validate-branch-name --types=... --issueless-types=chore,... --workflow=trunk --branch chore/devkit-1.19.0
Branch name 'chore/devkit-1.19.0' does not follow the convention ...
$ validate-branch-name --types=... --issueless-types=chore,... --workflow=trunk --branch chore/devkit-1-19-0
Branch name OK: chore/devkit-1-19-0
```

But `docs/MIGRATION.md` itself suggests exactly the rejected shape for an upgrade branch:

> offers to create and switch to `chore/devkit-upgrade-<version>` for you

where `<version>` is a release tag like `1.19.0` — so devkit's own documented/offered branch name for its own
upgrade workflow fails devkit's own branch-name hook and the matching CI branch-name gate. Hit for real doing a
1.18.0 -> 1.19.0 upgrade on a consumer repo whose process (and this repo's own architect tooling) names the branch
`chore/devkit-1.19.0`.

## Suggested fix

Either:
1. Allow a dot in the slug charset (it's unambiguous: `chore/devkit-upgrade-1.19.0` has no issue-number prefix to
   confuse it with), or
2. Change the `docs/MIGRATION.md` suggested name (and any `--version`-driven auto-offer) to a dot-free form, e.g.
   `chore/devkit-upgrade-1-19-0`.

Option 1 seems better: `X.Y.Z` is how every devkit release is spelled everywhere else (`.vig-os` `DEVKIT_VERSION`,
flake refs, changelog headings), so a branch name built from it reads oddly with dots stripped.
