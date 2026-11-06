---
type: issue
state: open
created: 2026-11-05T23:59:52Z
updated: 2026-11-05T23:59:52Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2049
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T09:11:28.326Z
---

# [Issue 2049]: [init-workspace.sh: placeholder substitution uses GNU-only grep -lZ / sed -i, fails natively on macOS (BSD userland)](https://github.com/vig-os/devkit/issues/2049)

Rendering natively (container-free, as scripts/consumer-matrix/render-cell.sh does, and as needed on hosts without a container runtime — see #1824) on macOS 26 with BSD userland, `assets/init-workspace.sh` (1.18.0, around line 3988) pipes candidates into `xargs -0 -r grep -lZ … | xargs -0 -r sed -i "s/…/…/g" --`. On BSD grep `-Z` means *decompress* (not NUL-terminate output), and BSD `sed -i` needs a suffix argument, so the substitution step fails (observed: renderer exit 123) and placeholders stay unrendered; failures are partly masked by `2>/dev/null || true`. Workaround used downstream (gerchowl/magpie#6): put GNU grep/sed first on PATH. Suggest either requiring/invoking GNU tools explicitly via the flake's toolchain, or a portable implementation (e.g. `grep -l --null` is also GNU-only; a small python/perl substitution would be portable), plus a consumer-matrix cell on macOS.
