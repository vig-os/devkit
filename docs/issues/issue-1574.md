---
type: issue
state: open
created: 2026-08-28T12:00:24Z
updated: 2026-08-28T12:15:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1574
comments: 1
labels: bug, priority:medium, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-28T14:15:35.207Z
---

# [Issue 1574]: [[BUG] pymarkdown fix-mode hook: fixer crashes on a common list idiom and silently rewrites document semantics (pin 0.9.23; all reproduced on upstream 0.9.39)](https://github.com/vig-os/devkit/issues/1574)

## Summary

The flake-generated `pymarkdown` hook runs `pymarkdown -c .pymarkdown fix` (#1170), with modify-and-fail semantics. Field use in exo-fleet (exo-pet/exo-fleet#229, landed as exo-pet/exo-fleet#427) found that the **fixer is unsafe on a very common documentation idiom** — fenced code blocks indented inside ordered list items — and that two rules' fixes **change document meaning**, not formatting. Every finding below was reduced to a synthetic reproducer and verified against both the devkit pin (**0.9.23**) and the current upstream release (**0.9.39**): *all of them reproduce on 0.9.39*, so a version bump alone is not a fix.

The danger is amplified by the hook's own semantics: on "files were modified by this hook", the natural operator move is re-add and re-commit — which is exactly how a semantics-changing rewrite lands in history as an unreviewed "lint fix". The hook comment in `nix/hooks.nix` also states fix "rewrites auto-fixable violations and exits 0 while *tolerating* unfixable ones"; bug 1 below violates that contract (hard failure on ordinary content).

## Bug 1 — `BadPluginFixError` crash (MD029 × MD031 fix conflict)

A numbered list that continues across a heading (runbook "phase" style) *and* contains an unspaced fence crashes the whole fix run. 13-line reproducer:

````markdown
# Repro

## Phase A

1. Step one.
2. Step two.

## Phase B

3. Step three:
   ```sh
   echo three
   ```
4. Step four.
````

```text
BadPluginFixError encountered while scanning 'conflict.md':
Multiple plugins (MD029 and MD031) are in conflict about fixing the token.
```

Identical on 0.9.23 and 0.9.39. In exo-fleet this hit 6 of 73 documents.

## Bug 2 — MD031 fixer de-indents fences inside list items (silent corruption)

With two consecutive list items each carrying an indented fence, the first is fixed correctly and the **second is dumped to column 0**, its content and closing fence left at the old indent, the item's continuation paragraph pulled out of the list, and trailing-whitespace lines left behind. 12-line reproducer:

````markdown
# Repro

1. First step:
   ```sh
   echo one
   ```
2. Second step:
   ```sh
   echo two
   ```
   Trailing note.
3. Third step.
````

Output (byte-identical damage on 0.9.23 and 0.9.39):

````markdown
2. Second step:
   
```sh
   echo two
   ```
   
Trailing note.
3. Third step.
````

This one exits "success", so it survives an inattentive re-commit.

## Bug 3 — `pyml` pragmas gate `scan` but not `fix`

`<!-- pyml disable-next-line ol-prefix -->` suppresses the scan finding, but `fix` renumbers the list anyway (verified 0.9.23 and 0.9.39). The documented escape hatch does not work in the mode the hook runs in.

## Two hazards that are "by design" but unsafe to auto-apply

- **md029 (ol-prefix)** renumbers ordered lists. Deliberate continuation numbering (steps 9., 10. resuming after a heading, referenced in prose as "step 9") is rewritten to per-list 1..n — a semantic change to a runbook, and per bug 3 there is no per-site opt-out.
- **md046 (code-block-style, "consistent")** converts fenced blocks to indented ones by **deleting the fence markers**, dropping language tags and breaking indentation when the blocks sit inside lists.

Related in the same class: a wrapped prose line beginning `+ ` parses as a list item, and **md004** "fixes" the marker to `-` — silently turning a textual *plus* into a *minus*. exo-fleet had seven such lines across ADRs and a compliance record.

## Why this is a devkit issue

The scaffolded `.pymarkdown` does not disable md029/md046, so **every consumer that enables the hook is exposed**; exo-fleet's mitigations live only in its own repo (`.pymarkdown` disables both, blank lines were inserted by an indentation-preserving script instead of the MD031 fixer, and the CLAUDE.md warns against bare `pymarkdown fix`). Devkit owns both remediation levers: the scaffolded config and the version pin.

## Proposed actions

1. **Scaffold-level mitigation now:** ship `md029` and `md046` disabled in the scaffolded/managed `.pymarkdown` (fix-mode is the reason; scan-only consumers could re-enable), and note the trap in the hook comment in `nix/hooks.nix`.
2. **File the three bugs upstream** (jackdewinter/pymarkdown) with the reproducers above — upstream has an active MD031-in-containers fix trail (their #1352/#1379/#1380/#1568), but as of 0.9.39 none of the three is fixed.
3. **Do not treat a pin bump as the fix** — re-test the reproducers on any future bump before relying on it.

Refs: exo-pet/exo-fleet#229, exo-pet/exo-fleet#427
---

# [Comment #1]() by [c-vigo]()

_Posted on August 28, 2026 at 12:15 PM_

Proposed action 2 is done — the three bugs are filed upstream with the synthetic reproducers, all verified on 0.9.23 and 0.9.39:

- jackdewinter/pymarkdown#1672 — BadPluginFixError (MD029×MD031 fix conflict) on a list resuming after a heading with an unspaced fence
- jackdewinter/pymarkdown#1673 — MD031 fix de-indents the second of two consecutive in-list fences to column 0 (exits 0, reports Fixed)
- jackdewinter/pymarkdown#1674 — pragmas suppress scan but fix applies anyway (disable-next-line ol-prefix → list renumbered)

Remaining on this issue: action 1 (ship md029/md046 disabled in the scaffolded .pymarkdown + hook-comment note) and action 3 (re-test these reproducers before trusting any pin bump — #1672/#1673/#1674 are the watch list for when a bump becomes worthwhile).

