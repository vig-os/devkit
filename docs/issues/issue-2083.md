---
type: issue
state: open
created: 2026-11-17T19:35:24Z
updated: 2026-11-17T19:35:24Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2083
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:44.200Z
---

# [Issue 2083]: [.vulnixignore: fzf exceptions use bare CVE keys, so an fzf bump won't re-gate them](https://github.com/vig-os/devkit/issues/2083)

The two fzf entries in `.vulnixignore` (`CVE-2026-53432`, `CVE-2026-53433`) are bare CVE ids. Every other awaiting-upstream entry uses the exact `CVE@pname@version` form, so that a build of the package at another version is gated afresh. These two would stay excepted at any fzf version until their expiry, 2026-12-16 since #2081.

Ask: re-key them as `CVE-2026-53432@fzf@0.72.0` and `CVE-2026-53433@fzf@0.72.0`, using the exact pname and version strings the gate prints. Check whether any other entries use the bare form, and whether the policy in docs/CONTAINER_SECURITY.md should forbid it for new entries.

Found in the review of #2081. Related: #2052.
