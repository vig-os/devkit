---
type: issue
state: closed
created: 2026-07-15T08:43:14Z
updated: 2026-07-15T14:37:17Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1108
comments: 1
labels: refactor, priority:medium, area:image, effort:medium, semver:minor, security
assignees: none
milestone: Backlog
projects: none
parent: 1103
children: none
synced: 2026-07-15T20:04:04.064Z
---

# [Issue 1108]: [Evict perl from the image: rewrap neovim without wl-clipboard; retire perl 5.42 CVE exception](https://github.com/vig-os/devkit/issues/1108)

### Description

**perl 5.42.0 (55 MiB + perl-module stack) can be evicted from the image — and
with it the live perl CVE exception batch** in `.vulnixignore` (#1097/#1098,
"pending upstream stable fix"), which currently has to be maintained until
upstream perl stabilizes. Fewer packages, fewer exceptions to babysit.

perl has exactly **two anchors** in the closure (traced with
`nix why-depends`):

1. full `git-2.54.0` (send-email/svn) — removed by the interpreter-eviction
   sub-issue (`gitMinimal`), which this issue **depends on**;
2. `neovim → wl-clipboard → xdg-utils → perl` (+ File-MimeInfo, X11-Protocol,
   XML-Twig, libwww-perl, …) — the nixpkgs neovim wrapper bakes `wl-clipboard`
   as a clipboard provider. **In a headless container this is dead code**:
   there is no Wayland socket; the clipboard path that actually works over
   VS Code remote / SSH is **OSC52**, which nvim ≥ 0.10 uses natively.

Marginal saving: **~55–60 MiB** (perl + the wl-clipboard/xdg-utils perl-module
stack). The security-posture win (retired CVE exception) is the primary
motivation.

### Proposed mechanism

Rewrap neovim without the clipboard-provider PATH suffix. Note: the pinned
nixpkgs `neovim` exposes only `{ configure, extraMakeWrapperArgs }` via
`override` — there is **no clean provider knob** — so this needs
`wrapNeovimUnstable` with an explicit config (preferred) or `overrideAttrs` on
the wrapper to filter `wl-clipboard`/`xdg-utils` from the suffixed PATH.

Ensure OSC52 is the effective clipboard provider in the image (nvim ≥ 0.10
auto-detects when no X11/Wayland tools are present; verify with a headless
`:checkhealth clipboard` equivalent).

### Risk

- Clipboard inside a plain `podman exec` TTY without OSC52-capable terminal
  passthrough loses `"+y` — acceptable: that path never worked meaningfully in
  a container without a display socket anyway.
- Medium effort: neovim rewrap is fiddlier than a list edit; the rewrapped
  derivation is uncached (first CI build pays; cachix caches after).

### Verification

- `nix path-info -r .#devkitImageEnv | grep -E 'perl|wl-clipboard|xdg-utils'`
  returns **nothing**.
- The perl 5.42 entries in `.vulnixignore` are **removed** in the same PR and
  the nightly vulnix scan stays green.
- In the built image: `nvim --headless "+checkhealth provider.clipboard" +q`
  reports OSC52 (or no provider) without errors; nvim starts clean.

### Notes

Part of the image-slimming epic. **Depends on** the interpreter-eviction
sub-issue (`gitMinimal` removes perl's other anchor). `security`-relevant:
retires a live CVE exception rather than maintaining it.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

Implemented and merged to dev in #1128 (−108.3 MiB measured; perl/wl-clipboard/xdg-utils grep empty; perl CVE exception batch deleted).

