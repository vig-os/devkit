---
type: issue
state: open
created: 2026-10-30T00:32:40Z
updated: 2026-10-30T00:32:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1977
comments: 0
labels: bug, security
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-30T08:26:24.344Z
---

# [Issue 1977]: [CVE-2026-111497 (CVSS 9.8) in brotli 1.2.0 fails the release vulnix gate](https://github.com/vig-os/devkit/issues/1977)

Found by the 1.18.1 candidate run (https://github.com/vig-os/devkit/actions/runs/40979727177), job "Vulnix CVE Gate":

```
1 unexcepted HIGH/CRITICAL or unscored vulnix finding(s) (CVSS >= 7.0 or no score):
  - CVE-2026-111497 (CVSS 9.8) in brotli 1.2.0
```

It's not in `.vulnixignore` on dev or on `release/1.18.1`. Triage is needed: which closure paths pull brotli in, whether a fixed brotli is in the locked or a newer nixpkgs, and whether the finding applies to how devkit uses brotli. Resolve it by a dependency fix, or by an evidence-based register entry with a short expiry. Never a blanket exception.
