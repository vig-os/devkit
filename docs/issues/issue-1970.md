---
type: issue
state: open
created: 2026-10-29T19:20:47Z
updated: 2026-10-29T19:20:47Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1970
comments: 0
labels: chore
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:25.649Z
---

# [Issue 1970]: [site-leak-check: follow-up nits from S6 final review](https://github.com/vig-os/devkit/issues/1970)

Follow-ups from the final review of PR #1950 (S6 #1932). Each is a non-blocking finding.

1. **`site-leak-check -- .` crashes.** Passing the repository root as an argument raises an uncaught `IndexError` (`relative.parts[0]`, `site_leak_check.py` ~line 136) with a traceback. It fails closed (exit 1) and prints no private data, and pre-commit never passes `.`. Expected: a clean error, or treating it as "scan all", with a test.
2. **One-bytecode signal window.** A signal that arrives right at the start of the cleanup `finally`, before `cleaning = True`, would skip the protected delete and leave it to the `TemporaryDirectory` finalizer at exit. This was found by reading the code; a timed signal didn't hit it. Close the window by blocking signals before entering the cleanup path, or document why it's acceptable.
3. **Binary files skipped by the commit hook.** A file with a NUL byte is skipped by the commit hook (`types_or: [text, symlink]`) but scanned by the no-arg CLI and `--all-files`. This is documented in the README. Decide whether CI's `--all-files` scan is the intended backstop, and say so in §10's known limits.

Refs: #1932
