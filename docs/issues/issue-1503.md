---
type: issue
state: closed
created: 2026-08-14T06:58:50Z
updated: 2026-08-14T08:48:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1503
comments: 2
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:15.912Z
---

# [Issue 1503]: [[BUG] promote: mirror reset 403s (checkout extraheader overrides the App token) — and would DELETE the archive if it succeeded while #1502 is open](https://github.com/vig-os/devkit/issues/1503)

### Description

`promote-release.yml`'s final `reset-sync-mirror` job fails with a 403 on every
mirror-mode consumer. It embeds the Commit App token in the push URL
(`promote-release.yml:767`), but its `actions/checkout` step (`:738`) does not set
`persist-credentials: false`, so checkout's persisted
`http.https://github.com/.extraheader` Authorization header takes precedence over
the URL's userinfo. The force-push therefore authenticates as
`github-actions[bot]`, and the job declares `permissions: contents: read`
(`:730-731`), so GitHub refuses it.

**The 403 is the lesser half of this report.** Combined with #1502 — where the
sync-mirror archive fold silently commits nothing — a *successful* reset would be
**destructive**. The step force-pushes `sync/issue-mirror` onto `main`:

```bash
git push --force "$REMOTE_URL" "${MAIN_SHA}:refs/heads/sync/issue-mirror"
```

Its comment justifies that as safe:

> After the merged release PR, main carries the folded archive; the mirror
> re-bases onto it so divergence stays bounded (#1424). [...] The mirror is
> unprotected and its history is regenerated state — a force reset loses
> nothing

Every word of that is conditional on the fold having worked. With #1502 present,
`main` carries **no** archive, so the reset would move the mirror ref off the only
commit holding the issue/PR snapshots — 55 files on `vig-os/org-config`,
recoverable only via reflog/API until GC. On this release the 403 is the sole
reason the archive still exists.

So: two independent silent-ish failures whose *interaction* is data loss, and
neither issue alone conveys that. Please treat the ordering guard below as part of
the fix rather than a nice-to-have.

### Steps to Reproduce

1. A mirror-mode consumer (`DEVKIT_SYNC_TARGET=sync/issue-mirror`) — e.g.
   `vig-os/org-config`, devkit 1.9.0, trunk model.
2. Run the release train through to `promote-release.yml`.
3. Watch the final `Reset sync mirror onto main` job.

### Expected Behavior

The mirror is reset onto `main` using the Commit App identity — and only after
verifying that `main` actually carries the archive the mirror is being reset away
from, so a broken or skipped fold can never turn housekeeping into deletion.

### Actual Behavior

Three retries, all 403, job fails, promote run goes red **after** the release has
already been published and the PR merged — so the release is fine and the red run
is misleading about what actually happened.

Observed on `vig-os/org-config` v1.1.0
([run 31777608346](https://github.com/vig-os/org-config/actions/runs/31777608346)):

```text
From https://github.com/vig-os/org-config
 * branch            main       -> FETCH_HEAD
remote: Permission to vig-os/org-config.git denied to github-actions[bot].
fatal: unable to access 'https://github.com/vig-os/org-config.git/': The requested URL returned error: 403
Retry 1/3 failed (exit 128), waiting 5s...
...
ERROR: Command failed after 3 attempts: git push --force ***github.com/vig-os/org-config.git 63ec8e51b4b7a
```

Note `denied to github-actions[bot]` even though `APP_TOKEN` is non-empty and
present in the URL — that is the extraheader winning, not a missing secret.

Job outcomes in the same run, for scope: `Validate promote prerequisites` success,
`Publish GitHub Release` success, `Merge release PR to main` success,
`Cleanup git RC tags` success, `Reset sync mirror onto main` **failure**,
`Move floating tags` skipped.

### Environment

- **Devkit version**: 1.9.0, consumer `vig-os/org-config` (public)
- **Consumer config**: `DEVKIT_WORKFLOW=trunk`, `DEVKIT_MODE=direnv`,
  `DEVKIT_TAG_PREFIX=v`, `DEVKIT_SYNC_TARGET=sync/issue-mirror`,
  `DEVKIT_FLOATING_TAGS=` (empty)
- **Checkout**: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1)
- **Runner**: GitHub-hosted `ubuntu-24.04`

### Additional Context

This is the third defect surfaced by the first end-to-end run of the release train
on a real mirror-mode consumer, after #1479 (trunk render produced an unopenable
release PR) and #1502 (fold commits nothing, silently). All three share a shape:
green or plausible-looking automation that had never executed against a live
repository in this configuration. Mirror-mode promote in particular appears never
to have completed end to end — worth a deliberate rehearsal target rather than
three more consumer-discovered bugs.

Cross-check for whichever fix lands first: with #1502 fixed but this issue open,
the archive stays stranded on the mirror (harmless). With **this** fixed but #1502
open, the next promote deletes the archive. That ordering matters — please do not
ship this fix ahead of #1502 without the guard below.

### Possible Solution

**1. Credential fix (one line).** Set `persist-credentials: false` on the job's
checkout (`promote-release.yml:738`) so the embedded App token in the push URL is
actually used. Equivalent alternatives: drop the extraheader before pushing
(`git config --unset-all http.https://github.com/.extraheader`), or push with
`git -c http.extraheader= push --force ...`. `persist-credentials: false` is the
smallest and matches the pattern used elsewhere in the scaffold.

**2. Safety guard (please include).** Before force-pushing, assert that `main`
contains the archive the mirror is being reset away from — e.g. verify every
`docs/issues` / `docs/pull-requests` path present on the mirror exists at
`MAIN_SHA`, and fail (or skip with a `::warning::`) otherwise. Then a broken fold
degrades to a stale mirror instead of deleted snapshots, and the step's
"loses nothing" comment becomes true by construction rather than by assumption.

**3. Job permissions.** With the App token correctly in use, `contents: read`
remains right for the default token. Worth an inline comment recording that the
push deliberately does not use `GITHUB_TOKEN`, so nobody "fixes" the 403 later by
granting `contents: write` — which would work, but would push mirror resets under
the Actions identity and defeat the App-identity model.

Refs #1424, #1502.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 07:59 AM_

Cross-link: #1508 — the `floating-tags` job in the same workflow has the identical construction (App token in the push URL, default checkout, `contents: read`), so the fix shape landing here applies there too.

Two things #1508 adds that are worth recording on this issue:

1. **The precedence is now reproduced outside CI.** Against a private repo with the credential helper disabled: valid token in the extraheader + a deliberately bogus token in the URL userinfo still authenticates, while the bogus userinfo alone fails. The extraheader wins; the URL userinfo is never consulted. That is the mechanism behind this 403, confirmed rather than inferred.

2. **`persist-credentials: false` alone would not have been enough.** It fixes the push but leaves the job's `git fetch` unauthenticated, which is fine on a public consumer and broken on a private one. #1507 checks out *with* the App token instead, so fetch and push both carry the App identity.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 14, 2026 at 08:48 AM_

Fixed on `dev` in #1507 (`c7af6a0c`), together with #1502.

**Credential fix.** Not the suggested `persist-credentials: false` one-liner: that fixes the push but leaves the job's `git fetch` unauthenticated, which is fine on a public consumer and broken on a private one. The App token is now generated **before** `actions/checkout` and passed to it, so fetch and push both carry the App identity — the pattern `release-core.yml` already used. `contents: read` stays, with an inline comment recording why widening it would be the wrong fix.

**Safety guard — included, as asked.** A new `Verify main carries the mirror archive` step asserts that `main` holds every `docs/issues` / `docs/pull-requests` path the mirror carries; the force-push is gated on it and otherwise skips with a `::warning::`. Skip rather than fail: at promote the release is already published, and a red run there misrepresents what happened — the release-time guard in #1502 is where failing is actionable. The step's "a force reset loses nothing" comment is now true by construction.

**The mechanism is confirmed, not inferred.** Reproduced outside CI against a private repo with the credential helper disabled: a valid token in the extraheader plus a deliberately bogus token in the URL userinfo still authenticates, while the bogus userinfo alone fails. The extraheader wins; URL userinfo is never consulted.

That result generalised — #1508 was the same construction in the `floating-tags` job, fixed in #1509.

