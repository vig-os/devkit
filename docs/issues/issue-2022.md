---
type: issue
state: open
created: 2026-11-04T03:48:15Z
updated: 2026-11-04T03:48:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2022
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:29.958Z
---

# [Issue 2022]: [Typst content guards: follow-ups from the #2019 review (own-line else test, one-sided margins, dict fonts, std.-qualified set rules)](https://github.com/vig-os/devkit/issues/2022)

Follow-ups from the round-5 verification of #2019 (#1994 phase 3). None blocked the merge.

1. **Test gaps** (the code behaves correctly; nothing pins it):
   - `else` on its own line after `}`: deleting the else-continuation survives every test.
   - The prose case `#emph[Note] else table(s)`.
   - A margin override on one side only.
2. **Dict fonts.** A font given as a dict (`font: (name: …, covers: …)`) crashes `guard-style` (`fonts.map(lower)`). The guard falls back to plain compile and the runtime bypass check is lost. Handle the dict and array forms.
3. **Runtime check gaps** (via aliases):
   - `set page(background: none)` on pages without headings;
   - `flipped: true`;
   - font changes in an included file with no heading after them (consistent with the documented page-start/heading scope).
   Consider probing at page end, or with a page background/foreground hook in guard mode.
4. **Qualified set rules.** The source scan misses `set std.page(...)` and `set std.text(...)` (the runtime check catches page).

Refs: #1994
