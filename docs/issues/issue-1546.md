---
type: issue
state: closed
created: 2026-08-18T07:14:59Z
updated: 2026-08-20T07:53:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1546
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-20T12:22:21.446Z
---

# [Issue 1546]: [[BUG] just doctor warns 'commit signing: incomplete' for a tilde user.signingkey](https://github.com/vig-os/devkit/issues/1546)

### Description

`just doctor` reports `WARN commit signing: incomplete` for a correctly configured
SSH-signing setup whenever `user.signingkey` is a tilde path (`~/.ssh/<key>.pub`).

The guard at `justfile:71-73` (and the scaffolded copy at
`assets/workspace/justfile:49-51`) tests key readability with:

```sh
[ "$format" != "ssh" ] || [ -r "$signingkey" ] || [ "${signingkey#ssh-}" != "$signingkey" ]
```

`test -r` performs no tilde expansion — the shell only expands `~` as an
*unquoted literal* at the start of a word, never the contents of a variable. So
`signingkey="~/.ssh/github.pub"` is tested as a relative path named `~` and the
readability check always fails. Git itself *does* expand `~` in
`user.signingkey`, so signing works fine; only the diagnostic is wrong.

### Steps to Reproduce

1. Configure SSH commit signing with a tilde path:

   ```sh
   git config --global commit.gpgsign true
   git config --global gpg.format ssh
   git config --global user.signingkey '~/.ssh/github.pub'
   ```

2. In a scaffolded consumer repo, run `just doctor`.
3. Confirm signing genuinely works: `git verify-commit <a locally signed commit>`.

### Expected Behavior

```text
PASS commit signing: ssh key ~/.ssh/github.pub
```

The check should expand a leading `~/` before testing readability, since that is
what git does when it consumes the value.

### Actual Behavior

```text
WARN commit signing: incomplete (commit.gpgsign=true, gpg.format=ssh, user.signingkey=~/.ssh/github.pub)
```

while `git verify-commit` on the same machine returns:

```text
Good "git" signature for <redacted> with ED25519 key SHA256:<redacted>
```

The warning is a false negative: it tells a correctly configured host that its
signing is incomplete, which is exactly the failure mode `doctor` exists to rule
out.

### Environment

- **OS**: NixOS (Linux 7.1.6), x86_64
- **Delivery mode**: `direnv` (`DEVKIT_MODE=direnv`)
- **Devkit version**: 1.10.0 (consumer repo, freshly scaffolded)
- **Architecture**: AMD64
- **Shell**: bash

### Suggested Fix

Expand a leading `~/` into `$HOME` before the readability test, in **both**
copies (`justfile` and `assets/workspace/justfile`, which must stay in sync):

```sh
keypath="$signingkey"
case "$keypath" in
    "~/"*) keypath="$HOME/${keypath#\~/}" ;;
esac
if [ "$gpgsign" = "true" ] && [ -n "$signingkey" ] && \
    { [ "$format" != "ssh" ] || [ -r "$keypath" ] || \
      [ "${signingkey#ssh-}" != "$signingkey" ]; }; then
```

Keep reporting the original `$signingkey` in the PASS line so the output still
mirrors what is in git config.

Refs: #1448 (the recipe this check ships in)

---

# [Comment #1]() by [c-vigo]()

_Posted on August 20, 2026 at 07:53 AM_

Fixed on `dev` via #1551 (merge commit `9d37073c`), milestone 1.11.0.

The readability guard now expands a leading `~/` against `$HOME` before `test -r`, in both the devkit `justfile` and the scaffolded `assets/workspace/justfile`; the PASS line still reports the raw value so it keeps mirroring `git config`. Four bats tests pin it — two for the PASS case, two twins asserting a tilde path to a *missing* file still WARNs.

Verified on the reporting host:

```text
before: WARN commit signing: incomplete (commit.gpgsign=true, gpg.format=ssh, user.signingkey=~/.ssh/github.pub)
after:  PASS commit signing: ssh key ~/.ssh/github.pub
```

Consumers pick it up on their next upgrade — the fix is in the managed root `justfile`, which is regenerated, not in the preserved `justfile.project`.

