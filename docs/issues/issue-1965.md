---
type: issue
state: open
created: 2026-10-29T08:51:22Z
updated: 2026-10-29T08:51:22Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1965
comments: 0
labels: chore, area:testing
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:27.134Z
---

# [Issue 1965]: [test: workflow replay exactness nits from #1964 review](https://github.com/vig-os/devkit/issues/1965)

Nits from the final review of PR #1964 (#1963). None of them lets S8's replay pass wrongly today. Each is a divergence from the Linux runner, checked against `actions/runner` sources.

1. **Step env can override context variables.** A step's `env:` or `GITHUB_ENV` can override `GITHUB_*` (for example `GITHUB_REPOSITORY: x/y` prints `x/y`). The runner re-exports context variables after step env (`ScriptHandler.cs` around line 290), so it would print the real value.
2. **Context keys not exported.** `github.run_id`, `server_url` and `ref_name` aren't exported as `GITHUB_RUN_ID`, `GITHUB_SERVER_URL` and `GITHUB_REF_NAME`. `devkit-upgrade.yml:561` uses `${GITHUB_RUN_ID}`. It's caught only by that script's `set -u`. Export every `GITHUB_*` variable the runner derives from the context.
3. **Surviving mutants.** Deleting `RUNNER_TEMP`, removing `steps.pop(id)`, and ignoring a CR on the heredoc delimiter line each leave the tests green. Add tests that kill them.
4. **Smaller divergences.**
   - A seed for a later step is visible to earlier steps.
   - A UTF-8 BOM ends up inside the key name; the runner strips it.
   - `NODE_OPTIONS` is not blocked.
   - `if: ""` raises instead of meaning `success()`.
   - `=v` raises, though the runner accepts it.
   - Job `runs-on`, `needs`, `environment` and `permissions` are ignored silently. Document that callers supply those contexts, or refuse them.

Refs: #1963
