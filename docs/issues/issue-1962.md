---
type: issue
state: open
created: 2026-10-29T04:13:01Z
updated: 2026-10-29T04:13:01Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1962
comments: 0
labels: chore, area:testing
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:27.632Z
---

# [Issue 1962]: [test: expression evaluator exactness nits from #1960 review](https://github.com/vig-os/devkit/issues/1962)

Nits from the final review of PR #1960 (#1959). None of them can make the S8 gate pass wrongly. Two are surviving mutants.

1. **Dead check.** The `integer <= 2**31 - 1` check at `tests/github_expression.py:183` has no effect, because any index above Int32 max is already past the list length. Remove it or explain it in a comment.
2. **Whitespace trimming.** `str.strip()` trims more than C# `Trim()`: `'\x1c5' == 5` is true here but false on the runner. Narrow it to the runner's whitespace set and add a test.
3. **`Infinity`/`NaN` strings.** `Double.TryParse` matches these case-insensitively, so `'INFINITY' == fromJSON('1e400')` is true on the runner and false here. Check this against the runner and align it, or document it.
4. **Greek case mapping.** In `_ordinal`, `'ᾳ'=='ᾼ'` is false here but true on the runner. When the full uppercase of a character is two characters, the simple single-character mapping is skipped. Use the simple case mapping.
5. **Literals.** The `Infinity`/`-Infinity`/`NaN` literals raise here but are accepted by the runner. This is strict, so document it.
6. **CLI `-0`.** A whole-value `-0` prints `-0.0`. Match the runner's `-0`.

Refs: #1959
