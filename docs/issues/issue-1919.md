---
type: issue
state: open
created: 2026-10-26T19:00:21Z
updated: 2026-10-26T19:29:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1919
comments: 1
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-27T07:38:04.363Z
---

# [Issue 1919]: [gh-app-provision: single-use callback, exchange failure-path tests, --base-url validation](https://github.com/vig-os/devkit/issues/1919)

Follow-ups from the review of #1918 (gh-app-provision CLI, #1909):

1. **Bug: the callback can run twice.** In `packages/vig-utils/src/vig_utils/gh_app_provision.py` (~L226-253), `handle_callback` never checks `code_done`. A browser reload or a second request to `/callback` runs the exchange again. GitHub codes are single-use, so the replay fails, sets `self.error` (500), and the terminal can report a failure after the secrets were already written. Nothing leaks. Fix: once a code has been accepted, return early on any later callback, and add a test that replays it.
2. **Untested failure paths.** Nothing tests a timed-out (`subprocess.TimeoutExpired`) or malformed (`JSONDecodeError`) `gh api` exchange. Today both fall into the generic handler and print nothing secret. Add tests that pin the error message and that no secret appears in the output.
3. **`--base-url` isn't validated.** It should require an http(s) scheme. Passing `--host` together with `--base-url` should be rejected, or the precedence documented. Today `--host` is silently ignored.

Refs #1909

---

# [Comment #1]() by [gerchowl]()

_Posted on October 26, 2026 at 07:29 PM_

One more item from the review of #1920 (the docs and skill): step 1 of `plugins/devkit/skills/app-provision/SKILL.md` runs `/devkit:status` "so you do not create a second App". But `/devkit:status` only reports the fixed `RELEASE_APP_*`/`COMMIT_APP_*` secrets, so it misses an existing App under any other `<PREFIX>`. Before provisioning, the skill should check `gh secret list | grep <PREFIX>_` (already used in step 6). The skill's frontmatter description also has one over-long line.

