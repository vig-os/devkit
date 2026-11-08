---
type: issue
state: open
created: 2026-10-27T10:52:48Z
updated: 2026-10-27T10:52:48Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1948
comments: 0
labels: bug
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:12:57.247Z
---

# [Issue 1948]: [env-only lint follow-ups: unquoted endpoint in templated-YAML fallback, heredoc scope, vig-utils import path in tests](https://github.com/vig-os/devkit/issues/1948)

Follow-ups from the final review of #1943 (the #1908 S5 env-only lint, #1931):

1. **Missed finding in the fallback path.** In templated YAML that has to use the line-based fallback, an *unquoted* `endpoint_url: https://…` is not caught, because the fallback rule in `packages/vig-utils/src/vig_utils/check_hardcoded_endpoints.py` skips unquoted values for endpoint keys (`if key in ENDPOINT_KEYS and not quoted: continue`). The same line in plain, parseable YAML is caught. Make the fallback agree with the YAML path, and add a test using a Helm file that contains an unquoted literal endpoint.
2. **Heredoc bodies.** Lines inside a shell heredoc (`cat <<X … X`) that look like `AWS_ENDPOINT_URL=…` are flagged. That is defensible, since they may write a config file that gets committed. Decide and document whether heredoc bodies are in scope. If they are, keep the current behaviour and document the pragma. If not, skip heredoc bodies, with tests either way.
3. **Test import path.** In a fresh worktree, `uv run pytest` can't import `vig_utils.check_hardcoded_endpoints` without `packages/vig-utils/src` on `PYTHONPATH`. Check how the root test environment installs vig-utils; this is probably a pre-existing gap for every vig-utils module.

Refs #1931

