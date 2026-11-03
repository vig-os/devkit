---
type: issue
state: open
created: 2026-10-13T01:11:47Z
updated: 2026-10-13T01:11:47Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1877
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:40.355Z
---

# [Issue 1877]: [commit-msg validator: 'Refs must be the last line' rejects DCO sign-offs (git commit -s appends Signed-off-by after Refs)](https://github.com/vig-os/devkit/issues/1877)

## What happens
The scaffolded commit-message validator requires `Refs: #N` to be the **last non-empty line** ("Only one Refs line is allowed; it must be the last non-empty line"). `git commit -s`, the standard way to sign off under the Developer Certificate of Origin, appends `Signed-off-by:` **after** the existing trailers. So every DCO-signed commit made with `-s` fails the validator, even with every commit type in `DEVKIT_REFS_OPTIONAL_TYPES`.

## Seen in
gerchowl/nodd, which uses DCO (CONTRIBUTING.md) and is adopting devkit 1.19.0-rc1. A pre-mortem ran the validator on the commits of two open PRs: all 3 commits fail.

## Expected
`Refs:` may appear anywhere within the trailer block (RFC 822-style trailers as `git interpret-trailers` parses them). Other trailers after it, such as `Signed-off-by`, `Co-authored-by` or `Reviewed-by`, are allowed. Uniqueness of `Refs:` can stay.

## Workaround
Write `Signed-off-by:` before `Refs:` by hand and don't use `-s`. That's error-prone, and it fights the tooling every DCO project uses.

