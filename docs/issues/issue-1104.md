---
type: issue
state: closed
created: 2026-07-15T08:43:07Z
updated: 2026-07-15T14:37:09Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1104
comments: 1
labels: refactor, priority:medium, area:image, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: 1103
children: none
synced: 2026-07-15T20:04:05.688Z
---

# [Issue 1104]: [Restrict image glibcLocales to en_US.UTF-8 (rebind imageTools AND LOCALE_ARCHIVE)](https://github.com/vig-os/devkit/issues/1104)

### Description

`glibcLocales` is the second-largest single path in the image at **222 MiB**,
yet the image only ever sets `en_US.UTF-8` (`LANG`/`LC_ALL`/`LANGUAGE` in the
`buildLayeredImage` `config.Env`). We ship the *entire* upstream locale set and
use one locale.

Marginal saving (measured on `.#devkitImageEnv`): **~222 MiB → a couple of
MiB**, **zero functional impact** (host-forwarded `LANG` values are already
masked by the baked `LC_ALL=en_US.UTF-8`).

### Proposed mechanism

⚠️ **The image references `glibcLocales` in TWO places, and both must move to
the same overridden derivation** — otherwise the full archive stays in the
closure via the Env string reference and the image *grows*:

1. the `imageTools` entry (`flake.nix:685`), and
2. the OCI config env, `flake.nix:1202`:
   `"LOCALE_ARCHIVE=${pkgs.glibcLocales}/lib/locale/locale-archive"` — an
   interpolated store path, i.e. an image reference in its own right.

Bind once, use twice:

```nix
glibcLocalesEnUS = pkgs.glibcLocales.override {
  allLocales = false;
  locales = [ "en_US.UTF-8/UTF-8" ];
};
```

### Verification

- `nix path-info -Sh .#devkitImageEnv` drops by ~220 MiB.
- `nix path-info -r .#devkitImageEnv | grep glibc-locales` shows exactly ONE
  (small) derivation.
- In the built image: `locale -a` lists `en_US.utf8`; shell start emits no
  `Cannot set LC_*` warnings; `python3 -c "print('ñ')"` round-trips.

### Notes

Part of the image-slimming epic. Fully independent — can land first. The
overridden derivation is not in cache.nixos.org; first CI build pays,
vig-os.cachix.org caches after.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

Implemented and merged to dev in #1119 (−219.5 MiB measured). Will ship with the next release.

