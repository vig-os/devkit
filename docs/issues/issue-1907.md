---
type: issue
state: open
created: 2026-10-22T10:15:03Z
updated: 2026-10-22T10:15:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1907
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-23T07:18:49.252Z
---

# [Issue 1907]: [setup-devkit-toolchain: 'Configure host Nix' replaces the self-hosted runner's NIX_CONFIG instead of extending it](https://github.com/vig-os/devkit/issues/1907)

**Where:** `.github/actions/setup-devkit-toolchain/action.yml`, step **Configure host Nix** (mode `direnv`, host Nix present). It writes a fresh multi-line `NIX_CONFIG` to `$GITHUB_ENV`.

**Problem:** on self-hosted runners that ship Nix, the runner's service env often carries its own `NIX_CONFIG` with site settings: a local binary-cache substituter plus its public key, and `cores`/`max-jobs` sized to the runner's CPU limit. Because the step replaces the variable, every later step loses them. Builds then miss the local cache (slower, more egress), and `cores` falls back to the default, so a small runner can oversubscribe its CPU quota and run out of memory.

Seen on a downstream repo's first self-hosted (ARC) run: the dev shell rebuilt from upstream caches instead of the local substituter.

**Suggested fix:** append to the ambient value instead of replacing it, keeping the existing well-formedness guard (#1192/#1216):
```bash
{
  echo 'NIX_CONFIG<<DEVKIT_NIX_CONFIG_EOF'
  [ -n "${NIX_CONFIG:-}" ] && printf '%s\n' "$NIX_CONFIG"   # keep the runner's settings first
  echo 'experimental-features = nix-command flakes'
  ...
  echo 'DEVKIT_NIX_CONFIG_EOF'
} >> "$GITHUB_ENV"
```
Use `extra-substituters` / `extra-trusted-public-keys` (already used) so nothing overrides the runner's own lists. If the ambient value may be malformed (#1216), validate it with `nix config show` under that value and drop it only on error, with a warning.

**Test idea:** with an ambient `NIX_CONFIG` containing `extra-substituters = http://cache.example` and `cores = 2`, after the step `nix config show` still lists that substituter and `cores = 2`.
