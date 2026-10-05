---
type: issue
state: closed
created: 2026-09-28T08:27:32Z
updated: 2026-09-28T09:30:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1739
comments: 1
labels: docs, priority:low, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:56.516Z
---

# [Issue 1739]: [[DOCS] No creation runbook for the vigos-devkit-upgrade App the scaffold depends on](https://github.com/vig-os/devkit/issues/1739)

### Description

The `vigos-devkit-upgrade` GitHub App is the machine identity behind the scaffolded
`devkit-upgrade.yml` workflow (`assets/workspace/.github/workflows/devkit-upgrade.yml:18-24`, the
grant header pointing at #1302), which mints an installation token from the `vig-os` org secrets
`DEVKIT_UPGRADE_APP_CLIENT_ID` / `DEVKIT_UPGRADE_APP_ID` / `DEVKIT_UPGRADE_APP_PRIVATE_KEY`. That
App has **no creation runbook anywhere**: this repo has no `docs/runbooks/` directory at all, and
`grep -rn "Where can this GitHub App be installed"` over it returns nothing. Its grant, its
visibility, its install targets and its key rotation are therefore reconstructible only from the
live App and from a comment in another repo's config.

`vig-os/org-config#271` closed the narrow half of this: the App's **visibility** posture (public —
"Any account" — because it is installed on `exo-pet` as well as `vig-os`) is now recorded as an
`APP VISIBILITY DECISION` comment beside the `DEVKIT_UPGRADE_APP_*` declarations in
`otterdog/vig-os/vig-os.jsonnet`, the App's only appearance in code, with its accepted costs and a
`GET /app/installations` sweep tied to key rotation. That was deliberately the cheap option, and it
leaves the larger one — a proper creation runbook, in the repo that owns the scaffold — open.

What is missing is the procedure a human needs if this App is ever recreated, re-permissioned, or
its key rotated by someone who did not create it: App name/slug and owner, homepage, webhook off,
the exact five permissions (`contents`, `issues`, `pull_requests`, `workflows` write and `metadata`
read), *Where can this GitHub App be installed?*, which orgs it is installed on and at what scope,
which org secrets carry its credentials and which repositories those lists must name, and the
rotation steps.

### Documentation Type

Add new documentation

### Target Files

- `docs/runbooks/devkit-upgrade-app.md` (new; the directory does not exist yet)
- Mirror the structure of `vig-os/org-config`'s `docs/runbooks/github-app.md` (Purpose,
  Prerequisites, Create the App, Permissions, Webhooks, Visibility, Installation, Bootstrap
  secrets, Key rotation, What this App must NOT be given)
- Cross-reference from `assets/workspace/.github/workflows/devkit-upgrade.yml`'s existing grant
  header, so the workflow points at the runbook instead of restating the grant

### Related Code Changes

Follows up on `vig-os/org-config#271` (visibility decision recorded in the org config) and its
precedent `vig-os/org-config#261` (the engine App's runbook Visibility section). The App exists
because of #1302; the ID-form rename is #1365.

### Acceptance Criteria

- [ ] A runbook for the `vigos-devkit-upgrade` App exists in this repo and states the grant,
      the visibility setting, the install targets and the key-rotation procedure
- [ ] The visibility paragraph links to the recorded decision in `vig-os/org-config` rather than
      re-deciding it, and says which repo is the source of truth for the credential lists
- [ ] Key rotation includes the `GET /app/installations` inventory sweep (the only compensating
      control for a public App's install page)
- [ ] The scaffolded `devkit-upgrade.yml` header links to the runbook

### Changelog Category

Added

### Additional Context

Not urgent: the App exists, works, and its visibility posture is now written down on the
`org-config` side. This matters the day the App has to be recreated or handed over — the grant is
`contents` / `issues` / `pull_requests` / `workflows` write, so reconstructing it by guesswork is
how an App ends up wider than it needs to be.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 28, 2026 at 09:30 AM_

Done on `dev` in #1742 (merge `81e30a8b`).

`docs/runbooks/devkit-upgrade-app.md` (new; the directory did not exist) mirrors `vig-os/org-config`'s `docs/runbooks/github-app.md` structure — Purpose, Prerequisites, Create the App, Permissions, Webhooks, Visibility, Installation, Bootstrap secrets, Key rotation, What this App must NOT be given.

Against the acceptance criteria:

- [x] Runbook exists and states the grant (`contents`/`pull_requests`/`workflows`/`issues` write + `metadata` read, with `issues:write` marked as the one optional grant), the visibility setting, the install targets and key rotation
- [x] The visibility paragraph links to the recorded decision (`vig-os/org-config#271` and the `APP VISIBILITY DECISION` comment at `otterdog/vig-os/vig-os.jsonnet:115-181`) rather than re-deciding it, and names that repo as the source of truth for the credential lists
- [x] Key rotation step 6 is the mandatory `GET /app/installations` inventory sweep
- [x] The scaffolded `devkit-upgrade.yml` header links to the runbook instead of restating the grant

**Two gaps are flagged in the runbook for live verification rather than guessed**, since no source read for it states them: the App's display name / homepage URL, and the installation *scope* ("All repositories" vs selected) on each org. The `exo-pet` installation id `151387251` is recorded because the org-config jsonnet states it; the scope alongside it is not.

Note on the header link: it is an absolute `blob/main/…` URL, not a relative path, because `docs/` is not shipped into the scaffold and a bare relative token fails `test_scaffold_has_no_unshipped_path_references`. It resolves once the runbook reaches `main` with the next train, which is also when the amended header reaches consumers via a released image — so the two land together outside of the RC window.

One deliberate tradeoff worth knowing: moving the grant into the runbook means the header no longer says at the point of use that `issues:write` is the skippable one. That is the SSoT outcome this issue asked for, but it is a real loss of locality.

