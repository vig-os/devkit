---
type: issue
state: closed
created: 2026-08-13T10:19:03Z
updated: 2026-08-14T13:39:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1497
comments: 1
labels: bug, priority:medium, area:ci, effort:medium, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:17.266Z
---

# [Issue 1497]: [Upgrade staleness is unobservable on both axes: the auto-bump grep misses most consumers, and scaffold-drift compares the pin to itself](https://github.com/vig-os/devkit/issues/1497)

Found auditing the Rust pack's upgrade story. This is a mechanism that exists, does not apply, and says nothing about it — the failure class this org keeps hitting.

## The auto-bump silently does not apply

`devkit-upgrade.yml` runs weekly and calls `install.sh --force`, which advances the consumer's devkit flake input. That advance is guarded by an **anchored grep** (`install.sh:1093`):

```sh
grep -qE '^[[:space:]]*vigos\.url[[:space:]]*=[[:space:]]*"github:vig-os/devkit"'
```

It matches only an input **named `vigos`** at the **unpinned** URL. `gerchowl/filesender` has:

```nix
devkit.url = "github:vig-os/devkit/dev";
```

Different name, pinned ref — **no match, no bump, no message.** The weekly upgrade job runs, reports success, and leaves the flake input untouched. Nothing tells the consumer that the part of the upgrade they most likely care about was skipped.

Both deviations are legitimate: `flake.nix` is a `PRESERVE_FILE`, so a consumer naming their input `devkit` is doing nothing wrong, and pinning a ref is normal.

## And nothing else covers it

`scaffold-drift` cannot: it resolves its comparison image **from the consumer's own `DEVKIT_VERSION` pin**, so it compares the pin against itself and reports clean. Being behind is invisible to it by construction — filesender sat two minor versions behind (1.6.0 vs 1.8.0) with a green drift check.

So there are two independent staleness axes and **neither is observable**:

| axis | mechanism | works? |
|---|---|---|
| scaffolded files | `scaffold-drift` | compares the pin to itself |
| flake input (where the Rust pack lives entirely) | `install.sh` auto-bump | greps for a name/URL most consumers do not have |

## Suggestions

Not a recommendation — the trade is devkit's:

1. **Make the grep name-agnostic**: match any input whose URL is `github:vig-os/devkit` with an optional `/<ref>` suffix, rather than one literal spelling.
2. **Report the skip.** If the auto-bump declines, say so in the job summary and the upgrade PR body. A silent decline is the whole bug; a loud one is a decision the consumer can make.
3. **Report the pin, not just the drift.** `scaffold-drift` (or a sibling) should compare `DEVKIT_VERSION` against the latest release and say "you are N releases behind", which is the question it currently cannot answer.
4. Consider a `mkRustProject` eval-time notice when the resolved devkit is much older than the pack it is building — the same "loud rather than silent" discipline #1427 and #1488 applied.

## Acceptance

- [ ] A consumer whose input is named anything, pinned or not, either gets bumped or is **told** why not
- [ ] Something, somewhere, answers "is this repo behind?" without the answer being derived from the repo's own pin

Refs: #1400, #1488

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 01:39 PM_

Delivered by #1514 (merged to dev). Both acceptance criteria met: (1) the flake auto-bump is keyed on the github:vig-os/devkit URL — any-name floating inputs are advanced, pinned refs (?ref=X or /X) are skipped with a printed reason, and every install.sh --force run emits one flake-bump: line that devkit-upgrade.yml surfaces in the adoption PR body and step summary; the #1093 skew warning learned the same discovery. (2) The new warn-only devkit-staleness job in the scaffolded ci.yml compares DEVKIT_VERSION against the latest devkit release — not derived from the repo's own pin — and annotates PRs with the behind-count. Suggestion 4 (mkRustProject eval-time notice) was deliberately left out; say the word if it should become its own issue.

