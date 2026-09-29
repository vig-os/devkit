---
type: issue
state: closed
created: 2026-09-28T08:15:28Z
updated: 2026-09-28T09:30:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1738
comments: 1
labels: docs, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:56.903Z
---

# [Issue 1738]: [[DOCS] DEVKIT_COMMIT_APP_ENVIRONMENT guard comment says UNQUOTED, but the renderer single-quotes](https://github.com/vig-os/devkit/issues/1738)

## Description

The `DEVKIT_COMMIT_APP_ENVIRONMENT` validation guard in
`assets/init-workspace.sh` describes the value as being rendered **unquoted**,
which contradicts the renderer that actually emits it. The comment above the
guard (around line 515) reads:

> Commit-App environment binding (#1710): the value is spliced verbatim into the
> rendered workflows as an UNQUOTED YAML scalar through a sed replacement, so —
> exactly as for `DEVKIT_SYNC_TARGET` above — the LOAD-BEARING guard is a strict
> charset allowlist.

`render_commit_app_environment()` (around line 2351) both documents and
implements the opposite, and explains why quoting is required: an unquoted
scalar would let YAML type the value (`true` as a boolean, `0755` as integer
493, `1e3` as a float), handing GitHub a non-string `environment` that it
rejects at dispatch and that `actionlint` does not flag — so the first failure
would surface in a consumer's repository, not here.

Verified against the live 1.17.0 render: the key is emitted single-quoted, and
values `true`, `no`, `0755` and `1e3` all parse back as Python `str` via PyYAML,
never as `bool`/`int`/`float`.

The guard's *reasoning* is unaffected and still correct — it refuses `'` along
with everything else that would need escaping, which is precisely what makes the
quoted splice safe. Only the word `UNQUOTED` is wrong, and it appears to be
carried over from the `DEVKIT_SYNC_TARGET` guard directly above, which does
render unquoted.

## Impact

Comment-only; no rendered byte changes and no consumer-visible effect. It is
worth fixing because the comment states the inverse of the invariant the
adjacent code relies on, which is the kind of thing that licenses a later
"simplification" that drops the quoting.

## Suggested change

Reword the guard comment to say the value is rendered as a **single-quoted**
scalar, and state that the charset allowlist stays load-bearing because it
refuses `'` (so no escaping is ever needed). Keep the cross-reference to
`DEVKIT_SYNC_TARGET` but make the quoting difference between the two explicit
rather than implying they behave alike.

## Note on delivery

This cannot ride the release-neutral lane: `assets/init-workspace.sh` is baked
into the image, so editing even a comment moves `devkitImage`'s derivation path
and gate 2 will refuse it. It needs a normal train.

## Provenance

Found during the live RC validation of `1.17.0-rc1` (tier 3, the
`DEVKIT_COMMIT_APP_ENVIRONMENT` render checks); all six render checks passed and
this was the only finding. Not a release blocker, so 1.17.0 shipped with it.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 28, 2026 at 09:30 AM_

Fixed on `dev` in #1740 (merge `66ba41fb`).

The guard comment now states that `DEVKIT_COMMIT_APP_ENVIRONMENT` is rendered as a **single-quoted** YAML scalar, says the charset allowlist stays load-bearing because it refuses `'` (so no escaping is ever needed), and makes the quoting difference from `DEVKIT_SYNC_TARGET` explicit instead of implying the two behave alike.

Verified rather than taken from the issue text: the splice really is `sed -i "/^  \${job}:\$/a\\    environment: '\${env_name}'"`, and the guard regex `^[A-Za-z0-9][A-Za-z0-9._-]*$` really does exclude `'`. The `DEVKIT_SYNC_TARGET` comparison also checks out and is now phrased as a genuine difference: that key's renderer mixes single-quoted YAML splices (`init-workspace.sh:2068-2069`) with a bare CLI-argument splice (`:2113`), which is where the original 'UNQUOTED' wording was carried over from.

Comment-only: 11/-8 lines, all inside the `#` block. The guard's `if` and `render_commit_app_environment()` are byte-identical, and no changelog entry was added since a code comment has no user-visible impact.

