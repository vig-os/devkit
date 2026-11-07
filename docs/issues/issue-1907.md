---
type: issue
state: open
created: 2026-10-22T10:15:03Z
updated: 2026-11-06T17:29:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1907
comments: 2
labels: none
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-11-07T08:37:43.492Z
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
---

# [Comment #1]() by [irenecortinovis]()

_Posted on November 6, 2026 at 03:50 PM_

Still seen on the ksb self-hosted runners on 2026-11-06. Small-runner jobs spend most of their time in "Set up devkit toolchain", fetching from cache.nixos.org instead of the runner's configured substituter (measured earlier: about 11 min of setup against about 1 min of work per job, MorePET/gPET-sim#349). Under load this pushes jobs into their timeouts:
- 15-minute cancellations on Lint & Format and Commit Messages (for example MorePET/gPET-sim2listmode run 42108932873);
- the 2-minute `Resolve toolchain` limit, reported separately.

A fix here would shorten every job and free runners sooner.


---

# [Comment #2]() by [gerchowl]()

_Posted on November 6, 2026 at 05:29 PM_

FYI from the ksb side: exo-pet/exo-fleet#1101 ships a workaround for ARC runner pods on ksb that keeps the ksb attic substituters and 'cores = buildJobs' alive across the pre-devkit#1916 setup-devkit-toolchain NIX_CONFIG rewrite. The seed init container now writes /nix/etc/nix.conf with the ksb extra-substituters + extra-trusted-public-keys + cores, and the runner env adds NIX_CONF_DIR=/nix/etc (a separate name from NIX_CONFIG, so a GITHUB_ENV append that only rewrites NIX_CONFIG leaves nix.conf intact). Nix merges nix.conf before NIX_CONFIG and extra-* keys append across both.

Live-verified in a ksb pod with devkit main's current NIX_CONFIG shape overlaid (experimental-features + accept-flake-config + extra-substituters = https://vig-os.cachix.org + extra-trusted-public-keys for vig-os): 'nix config show' returns cores = 4, substituters = cache.nixos.org, 10.0.2.2:8093 (proxy), 10.0.2.2:8092/ksb (attic), vig-os.cachix.org, trusted-public-keys = cache.nixos.org-1 ksb vig-os. 'Set up devkit toolchain' on exo-fleet#1094 Lint & Format: was cancelling at 20 min, now 7-11 min and end-to-end SUCCESS.

Independent of (and complementary to) #1916; the ksb workaround lives in the runner pod template so it stays useful for any other ksb consumers until devkit#1916 is released and adopted.

