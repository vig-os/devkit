---
type: issue
state: open
created: 2026-11-03T14:07:03Z
updated: 2026-11-03T14:07:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2011
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:31.912Z
---

# [Issue 2011]: [Typst docs guards: follow-ups from the #2005 review (recipe-name clash, indent test coverage, lint claim, preview gaps)](https://github.com/vig-os/devkit/issues/2011)

Follow-ups from the reviews of #2005 (#1994 phase 1a). None blocked the merge.

1. **Recipe-name clash breaks every `just` command.** A consumer with its own `typst`, `typst-canonical` or `typst-probe` recipe who turns docs ON gets `just --list` rc=1 (recipe redefined in `justfile.devkit-docs`). The installer exits 0 and later blames a syntax error. Load the recipes as a just module (`mod docs 'justfile.devkit-docs'`), or detect the clash, skip the import and print a notice. Fix this before the first adopter.
2. **Indent coverage.** Four mutants of `rendered_hooks` survive because every test layout except one contains a `repo: local`. Add remote-only layouts with 4-space, 3-space and mixed-step indentation to LAYOUTS.
3. **Lint claim.** docs/NIX.md's "no new yamllint findings" is too strong for configs that already had findings, such as the pre-commit sample-config layout and indentless hook lists. Narrow the claim to configs that were clean, or match the consumer's dash spacing.
4. **`--preview` gaps.** It misses removing a stale marker block when docs is OFF and the justfile is already gone. It shows `-` for a consumer-owned `justfile.devkit-docs` that the real run keeps.
5. **Unhelpful error.** A hook restored without its managed `exclude:` fails with a bare `KeyError: 'exclude'`. Give it advice text.
6. **Crash safety.** `publish()` writes in place, but catches only `Exception`. A KeyboardInterrupt during the write can leave a truncated file, and the backup is deleted. Restore from the backup on BaseException.
7. **Deleted repo entry.** The docs block sits inside the consumer's first local repo. Deleting that repo entry silently deletes the block and leaves the patched excludes behind. Detect this and report it.

Refs: #1994
