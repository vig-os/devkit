---
type: issue
state: open
created: 2026-11-04T05:22:45Z
updated: 2026-11-04T05:22:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2029
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:28.909Z
---

# [Issue 2029]: [install.sh check_default_branch treats gh api's 404 JSON as the default branch name](https://github.com/vig-os/devkit/issues/2029)

Found in the review of #2027. `check_default_branch` captures stdout from `gh api repos/<origin>`. When the origin repo doesn't exist on GitHub, or isn't visible, `gh api` prints the 404 JSON body on stdout. The install is then refused with: the default branch is '{"message":"Not Found",…}'.

Fix: check gh's exit status and use `--jq .default_branch`, or otherwise parse the field. On failure, say clearly that the default branch could not be determined, and what to do. Add a test with a gh shim that returns 404.

Refs: #2021
