---
type: issue
state: open
created: 2026-08-12T14:23:14Z
updated: 2026-08-12T14:23:14Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1477
comments: 0
labels: bug
assignees: none
milestone: 1.8.1
projects: none
parent: none
children: none
synced: 2026-08-13T04:18:11.120Z
---

# [Issue 1477]: [[BUG] Smoke listener's wait-for-workflow matches a stale run — promote fires before the release exists](https://github.com/vig-os/devkit/issues/1477)

### Description

The smoke listener's "trigger a workflow, then wait for it" pattern can match a **stale, unrelated run** and report success without the dispatched run having started. On the 1.8.0 final this made `Trigger and wait for release workflow` return success in 1.5 seconds, and promote-release was then fired against a repo that had no `1.8.0` release yet.

The pattern appears three times in `assets/smoke-test/.github/workflows/repository-dispatch.yml`, all with the same shape:

| Capture | Trigger | Wait |
|---|---|---|
| `:572` prepare-release | `:584` | `:591` |
| `:741` release | `:752` | `:771` |
| `:907` promote-release | `:918` | `:928` |

Each captures a baseline:

```sh
BEFORE_RUN_ID="$(gh run list --workflow release.yml --branch "${WORKFLOW_REF}" --limit 1 --json databaseId --jq '.[0].databaseId // 0' 2>/dev/null || echo 0)"
```

then polls for `RUN_ID -gt BEFORE_RUN_ID` plus `status == completed`. The guard assumes the newest run on `${WORKFLOW_REF}` at capture time is the newest run the poll will ever see other than the one just dispatched. That does not hold:

- `--branch "${WORKFLOW_REF}"` (`dev`) filters by the run's ref. A run dispatched against a **different** ref is invisible to the capture but the poll can still surface a newer one, so the baseline is not a baseline for the same population.
- The dispatched run needs a moment to appear in the API. If the poll's first iteration lands in that window, `--limit 1` returns a previous run — already `completed`, and newer than a stale baseline — and the wait exits `success` immediately.
- Nothing ties the matched run to the dispatch: not the inputs, not the creation time, not a run-name marker.

### Steps to Reproduce

Observed on the 1.8.0 final, listener run [31603474367](https://github.com/vig-os/devkit-smoke-test/actions/runs/31603474367):

1. `Capture latest release run id` recorded `BEFORE_RUN_ID: 29848630377` — days old.
2. `Trigger release workflow` dispatched the final; run [31604068811](https://github.com/vig-os/devkit-smoke-test/actions/runs/31604068811) was created at `13:56:27`.
3. `Wait for release workflow completion` started `13:56:28` and printed `release workflow completed successfully` at **`13:56:29.5`** — matching run `31599958705` (the rc4 release from `13:09`), not the run just dispatched.
4. `Trigger and wait for promote-release` ran ~30s later and failed: `ERROR: No GitHub Release for tag 1.8.0`.
5. Run `31604068811` was still `in_progress` (`Test Finalized Release`) throughout, and completed successfully afterwards, creating tag `1.8.0` and its draft release.

### Expected Behavior

The wait step blocks until **the run this job dispatched** reaches a terminal state, and reports that run's conclusion.

### Actual Behavior

It reports the conclusion of whichever run happens to be newest and completed, which on a final release is the previous RC's run. Downstream jobs then act on a release that does not exist yet.

### Impact

Silent on candidates — `trigger-promote-release` is skipped for RCs, so nothing consumes the bogus success and the defect stayed invisible across rc1–rc4. On a **final** it fires every time: promote is dispatched before the release exists, the smoke chain reports failure, and the cross-repo gate blocks the upstream promote for a reason that is not real. Recovery today was a `gh run rerun --failed` once the release run had genuinely finished, but the gate had already reported a false negative — the worst failure mode for a gate.

### Possible Solution

Bind the wait to the dispatched run rather than to an ID ordering. Options, roughly in order of robustness:

1. **Stamp the dispatch and match on it.** Give the dispatched workflow a `run-name` carrying a unique token (the upstream tag, or `github.run_id` of the listener) and poll for a run whose `displayTitle`/`name` contains it. Unambiguous, survives both the visibility lag and the ref mismatch.
2. **Filter by creation time.** Record `DISPATCH_TS` immediately before `gh workflow run`, then require `createdAt > DISPATCH_TS` in addition to `status == completed`, and keep polling (rather than exiting) while no such run exists.
3. **Align the capture and poll filters** at minimum — the same `--workflow`, `--branch` and `--event` on both sides — so the baseline describes the population being polled. Necessary but not sufficient on its own; it does not close the visibility-lag window.
4. Require the run to be non-terminal at least once before accepting its conclusion, so a run that was already `completed` at first poll can never be matched.

Fix all three call sites together — they share the helper shape, and prepare-release and promote-release have the same exposure even though only the release one has bitten so far.

### Environment

devkit 1.8.0 (released), `assets/smoke-test/.github/workflows/repository-dispatch.yml`. Note the listener executes from devkit-smoke-test's **default branch**, so a fix needs the usual manual redeploy there before the next final.

### Changelog Category

Fixed

Refs: #1443, #1392

