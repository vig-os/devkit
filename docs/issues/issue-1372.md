---
type: issue
state: closed
created: 2026-08-07T14:47:01Z
updated: 2026-08-07T16:00:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1372
comments: 1
labels: docs, priority:low, effort:small, area:docs, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:59.227Z
---

# [Issue 1372]: [[DOCS] Community profile: rename CONTRIBUTE.md to CONTRIBUTING.md and add CODE_OF_CONDUCT.md](https://github.com/vig-os/devkit/issues/1372)

## Summary

Two gaps in the repository's GitHub **community profile**:

1. The contributing guide is named **`CONTRIBUTE.md`**. GitHub only recognises
   **`CONTRIBUTING.md`** (root, `docs/`, or `.github/`), so the "Contributing
   guidelines" row of `repos/vig-os/devkit/community/profile` is unchecked and no
   "Contributing guidelines" link is surfaced on new issues/PRs.
2. There is **no `CODE_OF_CONDUCT.md`**, so that row is unchecked too.

```console
$ gh api repos/vig-os/devkit/community/profile --jq '.files | keys'
# code_of_conduct: null, contributing: null
```

## (a) Rename `CONTRIBUTE.md` -> `CONTRIBUTING.md`

`CONTRIBUTE.md` is **generated**, so the rename is not just the file:

- `docs/templates/CONTRIBUTE.md.j2` -> `docs/templates/CONTRIBUTING.md.j2`
  (and the "Auto-generated from …" banner inside it)
- `docs/generate.py` — the `templates_to_generate` entry
- `.pre-commit-config.yaml` — the pymarkdown `exclude` for generated docs
- `.github/workflows/release.yml` — the `expected_doc` list in the docs
  regeneration guard
- `docs/templates/README.md.j2` (and the generated `README.md`) — the
  contributing link
- `docs/NIX.md` — three cross-references
- `.github/ISSUE_TEMPLATE/docs.yml` — the "generated docs must not be edited
  directly" note and the source-template URL (manifest-synced, so
  `assets/workspace/.github/ISSUE_TEMPLATE/docs.yml` follows automatically)

Use `git mv` so history follows. Historical records — `CHANGELOG.md` entries
below `## Unreleased`, `docs/issues/*.md`, `docs/pull-requests/*.md` — must be
left untouched.

## (b) Add `CODE_OF_CONDUCT.md`

Contributor Covenant **v2.1** standard text at the repository root, with the
enforcement contact pointing at the reporting channel already declared in
`SECURITY.md` (GitHub Private Vulnerability Reporting) so there is a single
source of truth for "how to reach the maintainers privately".

## Acceptance criteria

- [ ] `CONTRIBUTING.md` at the repo root, generated from
      `docs/templates/CONTRIBUTING.md.j2`; no `CONTRIBUTE.md` remains
- [ ] no live reference to `CONTRIBUTE.md` outside historical archives
- [ ] `just docs` / the `generate-docs` hook is a no-op after the rename
- [ ] `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) at the repo root
- [ ] `gh api repos/vig-os/devkit/community/profile` reports both files once
      GitHub's cache refreshes

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 04:00 PM_

Fixed on dev by PR #1376 (0b3cf554): CONTRIBUTE.md renamed to CONTRIBUTING.md (template, generator, hooks, release guard, and live cross-references all updated) and CODE_OF_CONDUCT.md (Contributor Covenant 2.1, enforcement contact pointing at the SECURITY.md reporting channel) added at the root. The community-profile checklist will reflect both once GitHub's cache refreshes after the merge to main.

