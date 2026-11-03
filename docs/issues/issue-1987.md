---
type: issue
state: open
created: 2026-11-02T13:38:10Z
updated: 2026-11-02T13:38:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1987
comments: 0
labels: docs, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T09:20:22.569Z
---

# [Issue 1987]: [Release cycle docs omit 'mark the release PR ready' before the final release; draft-gate failure points to the wrong recovery](https://github.com/vig-os/devkit/issues/1987)

## What happened
In a downstream repo (vig-os/vigil), `prepare-release.yml` opened the release PR as a **draft** (vig-os/vigil#181). The candidate `release.yml` run then succeeded, as #902 intends. The **final** run (vig-os/vigil run 41453826103) failed in `Release Core / Validate Release Core › Find and verify PR`:

```
ERROR: PR #181 is still in draft
```

Finalize never ran, the rollback no-op'd correctly, and an automatic failure issue (vig-os/vigil#184) was opened.

## The gap (docs, not the gate)
The gate itself is correct. `release-core.yml` (~l.285–300) explains that the final release burns the immutable tag, so the PR must be out of draft. But the consumer-facing docs never say so:
- `docs/DOWNSTREAM_RELEASE.md` describes `candidate` and `final` (l.29–30) and promote (l.18), but has no step "mark the release PR ready for review (`gh pr ready <n>`) before dispatching `release-kind=final`".
- The automatic failure issue tells the reader to "use a new release candidate to validate fixes, then re-run the final release". For a draft-gate failure that's the wrong recovery: nothing was finalized, and the only fix is to mark the PR ready and re-dispatch final. A new RC isn't needed.

## Proposal
1. Add the "mark ready" step to the release-cycle sequence in `docs/DOWNSTREAM_RELEASE.md` (and `RELEASE_CYCLE.md` if it lists the steps). Say that it's the cycle's deliberate "content is final" signal.
2. Have the validate step's error message name the fix: `ERROR: PR #N is still in draft — mark it ready (gh pr ready N) and re-dispatch release-kind=final`.
3. Make the failure issue's recovery text depend on the stage that failed. A pre-finalize validate failure needs no new RC.

