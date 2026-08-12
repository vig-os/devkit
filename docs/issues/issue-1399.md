---
type: issue
state: closed
created: 2026-08-10T12:21:29Z
updated: 2026-08-10T13:07:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1399
comments: 1
labels: chore, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:27.422Z
---

# [Issue 1399]: [[CHORE] Widen attestation retry backoff to survive multi-minute Rekor outages](https://github.com/vig-os/devkit/issues/1399)

### Chore Type

CI / Build change

### Description

The release workflow's SBOM/provenance attestation steps fail the whole `publish`
job when the public-good Sigstore transparency log (`rekor.sigstore.dev`) has a
multi-minute incident. The current outer retry is too short and too fast to ride
one out.

`release.yml` wraps each attestation in a two-attempt outer retry with a fixed
30-second gap:

```yaml
- name: Attest SBOM (attempt 1)
  id: attest_sbom
  continue-on-error: true
  uses: actions/attest@1e69f48...
- name: Wait before retrying SBOM attestation
  if: steps.attest_sbom.outcome == 'failure'
  run: sleep 30
- name: Attest SBOM (retry)          # no continue-on-error -> failure fails the job
  if: steps.attest_sbom.outcome == 'failure'
  uses: actions/attest@1e69f48...
```

The action already retries internally, so the outer layer is the *second* of two
nested retry layers. In `@actions/attest`'s `initBundleBuilder`:

```js
const DEFAULT_TIMEOUT = 10000;
const DEFAULT_RETRIES = 3;
```

These are handed to the `RekorWitness`, flow through `Rekor.createEntry` into
`fetchWithRetry(url, {timeout, retry})`, which wraps `make-fetch-happen` in
`promiseRetry` with `{retries: 3}` and the `retry` package's stock backoff
(factor 2, minTimeout 1s). It explicitly disables the fetch client's own retry
(`retry: false // We're handling retries ourselves`), so there is exactly one
internal layer.

Net effect per action step: **4 Rekor attempts at 0s / +1s / +2s / +4s, each with
a 10s timeout — roughly 47 seconds of coverage.** With the outer step the total
envelope is only about **2 minutes**, which is shorter than a typical Sigstore
incident.

None of this is tunable from the workflow. `action.yml` at the pinned SHA exposes
no timeout or retry inputs, and `src/attest.ts` calls
`attest({subjects, predicateType, predicate, sigstore, token})` without passing
`timeout`/`retry`, so the 10s/3 defaults always apply. The only tunable constants
in the action (`OCI_TIMEOUT = 30000`, `OCI_RETRY = 3`) apply to the registry push,
not to Rekor. There is no env-var override. **The outer backoff in `release.yml`
is therefore the only lever we control.**

Observed on 1.7.0-rc2
([run 31204672354](https://github.com/vig-os/devkit/actions/runs/31204672354),
issue #1390), where all 8 attempts fell inside one outage window:

| Time (UTC) | Step | Result |
|---|---|---|
| 18:11:26 -> 18:11:33 | Attest build provenance (attempt 1) | success, pushed to repository + registry |
| 18:11:33 -> 18:12:21 | Attest SBOM (attempt 1) | `InternalError: error creating tlog entry` / `FetchError: network timeout at https://rekor.sigstore.dev/api/v1/log/entries` (48s = 4 internal attempts) |
| 18:12:21 -> 18:12:51 | `sleep 30` | -- |
| 18:12:51 -> 18:13:39 | Attest SBOM (retry) | same failure (48s = 4 more internal attempts) |

1.7.0-rc1 hit the same failure mode, so this is recurring rather than a one-off.

Note that build provenance succeeded a minute before the SBOM step failed and was
already pushed, so the rollback left a published attestation for a rolled-back
digest -- the dangling-referrer case `ghcr-cleanup.yml` already handles. Not part
of this issue.

### Acceptance Criteria

- [ ] The outer backoff between attestation attempts is measured in minutes, not
      30 seconds, so the total envelope survives a typical multi-minute Rekor
      incident.
- [ ] Applied to both attestation pairs (build provenance and SBOM) so they
      degrade consistently.
- [ ] The final attempt still fails the job -- no silent skipping of attestation.
- [ ] The retry structure is not copy-pasted a third and fourth time; the four
      near-identical `uses:` blocks are consolidated or driven by a loop.
- [ ] Rendered-workflow tests still pass (`bats` -- note that rendered-template
      `actionlint` runs only in bats, not in `prek`).
- [ ] Exercised on a release candidate before the next final release.

### Implementation Notes

Target: `.github/workflows/release.yml`, lines ~1192-1234 (the two
attempt-1 / wait / retry triplets).

Sizing: a 3-4 attempt outer loop at 60s / 120s / 240s gives roughly 10 minutes of
coverage including the ~47s each attempt already spends internally, versus the
current ~2 minutes.

Shape worth considering rather than adding more duplicated steps: a single
`run:` step that loops with escalating sleeps and shells out, or a composite
action, since the same block is currently repeated four times. Any consolidation
must keep the `continue-on-error` semantics on all but the last attempt.

Explicitly out of scope: the undocumented `private-signing` input routes signing
to GitHub's internal Sigstore instance instead of public-good and would sidestep
`rekor.sigstore.dev` entirely, but it changes the attestation's trust semantics
to private provenance and defeats the point of publicly verifiable attestations
on a public image. Not a mitigation we want.

A larger alternative, if the outer backoff proves insufficient: decouple SBOM
attestation from the publish job's critical path so a Rekor incident degrades the
release rather than failing it. That is a bigger design change and should be its
own issue.

### Related Issues

Follow-up from #1390 (1.7.0-rc2 release failure, closed as transient).

### Priority

Medium

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 01:06 PM_

Fixed on `dev` via #1402 (merge commit `77acc655`), milestone 1.7.1.

**What shipped:**
- `.github/scripts/wait-for-rekor.sh` (new) — settles 30s, then probes `${REKOR_URL}/api/v1/log` every 30s until the transparency log answers or a 600s budget runs out. It always exits 0: deciding the release's fate is the retry step's job, and a non-zero exit here would abort the job before that retry ever ran.
- Both attestation waits in `release.yml` (provenance and SBOM) call the helper instead of `sleep 30`. Attempt/retry structure is unchanged — attempt 1 stays `continue-on-error`, the retry still fails the job.
- `publish` `timeout-minutes` raised 30 → 45. Publishing itself runs ~5min (measured across the 1.7.0 candidates) and two full waits can burn 20min, so the old ceiling would have failed the release on the *timeout* instead of letting the widened backoff work. A test pins the two values together so they cannot drift apart.

Coverage per attestation goes from ~2 minutes to ~12, and the common case gets faster — a short blip no longer costs a flat 30-second sleep.

**On the "no third and fourth copy" criterion:** met by not adding attempts at all. GitHub Actions cannot loop over a `uses:` step, so a 3rd and 4th attempt would have meant duplicating each attestation block again. Making the *wait* adaptive buys more coverage than extra attempts would have, at two `uses:` blocks per attestation — unchanged from before.

**Tests:** `tests/bats/wait-for-rekor.bats` (5) stubs `curl` and `sleep` to drive a simulated clock — returns when the log answers, keeps probing while it is down, gives up at the deadline without failing the step, probes the configured URL, always settles first. `tests/test_workflow_attest_retry_backoff.py` (8) pins the workflow shape. PR CI was 12/12 green including Integration and Image Tests.

**Still unproven, deliberately:** the last acceptance criterion — exercising this on a release candidate. The path only executes when an attestation actually fails, so PR CI cannot reach it. It gets its first real exercise whenever the next train meets a Rekor incident; if 1.7.1's candidates pass without one, that is not evidence either way.


