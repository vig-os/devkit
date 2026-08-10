---
type: issue
state: open
created: 2026-08-07T13:31:23Z
updated: 2026-08-07T13:31:23Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1366
comments: 0
labels: chore, priority:medium, area:ci, effort:small
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:00.995Z
---

# [Issue 1366]: [[CHORE] Drop the numeric App-ID fallback and retire *_APP_ID org secrets](https://github.com/vig-os/devkit/issues/1366)

### Chore Type

CI / Build change

### Description

Follow-up to #1365, which switches the stamped workflows to client-ID App
credentials but keeps a **backward-compatible fallback** so the rename rides a
minor: the `devkit-upgrade.yml` scaffold accepts the legacy numeric secret via

```yaml
client-id: ${{ secrets.DEVKIT_UPGRADE_APP_CLIENT_ID || secrets.DEVKIT_UPGRADE_APP_ID }}
```

and its preflight gates on *either* name (warning on the legacy one).

Once the last consumer is on the release carrying #1365, the fallback has no
remaining purpose. This issue removes it and coordinates the retirement of the
numeric `*_APP_ID` org secrets, per the migration principle from #1365: *no
numeric `*_APP_ID` secret is deleted while any pinned workflow still references
it* (cautionary precedent: `exo-pet/playground-carlos` sync-issues broke
silently for a week on a missing `COMMIT_APP_ID`).

### Acceptance Criteria

Preconditions (all must hold before starting):

- [ ] The devkit release carrying #1365 is adopted by **every** scaffold
      consumer in `vig-os` and `exo-pet` (including vig-os/h5v#6 and
      vig-os/scitadel#209, which need scaffold bumps first).
- [ ] `DEVKIT_UPGRADE_APP_CLIENT_ID` exists as an org secret in **both** orgs
      (creation tracked in exo-pet/org-config#20 and the vig-os org-config
      tracker).

Work:

- [ ] `assets/workspace/.github/workflows/devkit-upgrade.yml`: drop the
      `|| secrets.DEVKIT_UPGRADE_APP_ID` fallback from the `client-id:` input,
      the legacy branch of the preflight gate, and the legacy-name warning.
- [ ] `tests/test_workflow_devkit_upgrade.py`: assert the fallback expression
      and the legacy secret name are **gone** from the template.
- [ ] Changelog + release notes state that `DEVKIT_UPGRADE_APP_ID` is no longer
      read at all.
- [ ] After the release ships and all consumers adopt it: delete the numeric
      org secrets — `DEVKIT_UPGRADE_APP_ID` (vig-os and exo-pet) and
      `COMMIT_APP_ID` (vig-os only; exo-pet never had it). Deletion itself is
      org-config territory — check off here once done there.

### Implementation Notes

- The fallback works because GitHub accepts either the numeric App ID or the
  client ID as the App JWT issuer, and `actions/create-github-app-token`
  forwards the value verbatim — removing it is a pure simplification once no
  consumer depends on the legacy secret.
- `RELEASE_APP_ID` (vig-os) is also still present as an org secret and appears
  unreferenced since the Release App went client-ID-only; verify with a fleet
  grep and, if confirmed dead, retire it in the same org-config sweep.
- Removing the fallback is breaking only for a consumer that never created the
  new secret; the preconditions above make that set empty by construction.

### Related Issues

Follows #1365. Coordinates with exo-pet/org-config#20 and the vig-os
org-config secrets tracker. Consumer bumps: vig-os/h5v#6, vig-os/scitadel#209.
vig-os/tessera#364 uses its own App and is unaffected.

### Priority

Medium

### Changelog Category

Changed

