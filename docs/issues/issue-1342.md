---
type: issue
state: closed
created: 2026-08-04T10:15:34Z
updated: 2026-08-04T10:44:26Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1342
comments: 1
labels: bug, priority:medium, area:ci, effort:small, semver:patch, security
assignees: c-vigo
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:53.507Z
---

# [Issue 1342]: [[BUG] Red vulnix gate suppresses the SBOM steps, stripping the artifact exactly when it is needed](https://github.com/vig-os/devkit/issues/1342)

## Description

In `security-scan.yml`, the SBOM steps sit **after** the blocking `vulnix-gate`
step and carry no `if:` condition. A red gate fails the step, and the job stops
there — so the CycloneDX SBOM and the Trivy defence-in-depth (SBOM-mode) view
are never produced.

The result is inverted from what you want: the artifact is complete on green
runs, where nobody needs it, and stripped on red runs, where it is the evidence
you would use to triage the finding — cross-check the vulnix hit against Trivy,
confirm the package is really in the closure, and see what else ships alongside
it.

The `Upload vulnix findings + SBOM` step is already guarded with `if: always()`
and its comment says *"a red vulnix-gate is exactly when the findings are
needed"* — so the intent is on record; it just isn't carried through to the two
steps that generate half of what it uploads.

## Steps to Reproduce

1. Let the nightly `Scheduled Security Scan` run with an unexcepted HIGH/CRITICAL
   finding in the closure (e.g. the runs from 2026-07-31 through 2026-08-03,
   before #1327 landed).
2. `Gate on unexcepted HIGH/CRITICAL vulnix findings`
   (`security-scan.yml:158-163`) exits non-zero.
3. Download the `nix-image-cve-scan-<ref>` artifact.

## Expected Behavior

The artifact contains `vulnix-findings.json`, `vulnix-report.txt` **and**
`sbom-nix-cyclonedx.json` on every run that reaches the scan, red or green —
matching the stated intent of the `if: always()` upload step.

## Actual Behavior

On a red gate the artifact contains only the two vulnix files. Observed size
difference on the dev leg:

| Run | Gate | Artifact |
|-----|------|----------|
| 2026-07-30 (30523258723) | green | ~466 kB (with SBOM) |
| 2026-08-03 | red | ~17 kB (no SBOM) |

The `Build the Nix image for SBOM generation` step
(`security-scan.yml:165-169`) and `Generate Nix image SBOM (CycloneDX)`
(`:171-177`) are simply never reached.

## Environment

- **Workflow**: `.github/workflows/security-scan.yml` (both matrix legs, `main`
  and `dev`)
- **Runner**: ubuntu-24.04
- **Image Version/Tag**: n/a — CI-only defect, no image or code change involved
- **Architecture**: AMD64

## Additional Context

Spotted while working #1327 and confirmed again during the #1328 pin advance.
Not a regression: the ordering has been there since the SBOM steps were added,
and it only bites on a red gate, which until 2026-07-31 was rare.

Note the same job already handles a related case correctly — the Trivy SBOM-mode
scan carries `continue-on-error: true` so a Trivy failure cannot mask the vulnix
signal. This issue is the mirror image: a vulnix failure should not suppress the
Trivy/SBOM evidence.

## Possible Solution

Two options, either acceptable:

- **Add `if: always()`** to `Build the Nix image for SBOM generation` and
  `Generate Nix image SBOM (CycloneDX)`, matching the existing upload step. Note
  `always()` also runs on cancellation — `if: !cancelled()` is the tighter form.
- **Reorder**: move the SBOM build/generate steps *above* the gate, so the gate
  stays the last thing in the job and remains the job's pass/fail signal.

Reordering is probably cleaner — it keeps the gate as the final, unambiguous
verdict — but it does mean the image build runs before the gate on every run.
Since `nix build .#devkitImage` is largely cache-warm after `devkitImageEnv` has
already been built earlier in the same job, the added cost on a red run should
be small.

Acceptance criteria:

- [ ] A red-gate run uploads an artifact containing `sbom-nix-cyclonedx.json`
- [ ] The gate still fails the job on unexcepted HIGH/CRITICAL findings (it
      remains blocking — the tracking-issue automation keys on
      `vulnix-gate.outcome == 'failure'`)
- [ ] Both matrix legs (`main`, `dev`) behave identically
- [ ] TDD compliance (see .claude/skills/tdd/SKILL.md)

## Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 10:44 AM_

Fixed in #1343, merged to `release/1.6.0` as `3253bfa5`.

The three evidence steps (image build, CycloneDX SBOM, Trivy SBOM-mode) now run **before** the blocking gate. The gate is otherwise byte-for-byte unchanged — still blocking, still unconditioned, still the last checking step — so it remains the job's verdict and the tracking-issue automation keyed on `vulnix-gate.outcome == 'failure'` is unaffected.

**Acceptance criteria**

- [x] A red-gate run uploads an artifact containing `sbom-nix-cyclonedx.json` — enforced by `test_sbom_steps_precede_the_blocking_gate`; live confirmation waits for the next genuinely red gate (`dev` is green again after #1327/#1328)
- [x] The gate still fails the job on unexcepted HIGH/CRITICAL findings — `test_gate_stays_blocking` asserts no `continue-on-error` and no `if:`
- [x] Both matrix legs behave identically — the change is in the shared step list, above the matrix
- [x] TDD compliance — test committed red-first (`ace02b53`: 2 failed, 2 passed), implementation green (`63ebe2b3`: 4 passed)

**Verification:** `pytest -k workflow` 130 passed; `just precommit` full suite green; PR CI 12/12 green. The final test file was re-proven red against the original workflow by stashing only the workflow change, so the red-first evidence covers the assertions as they now stand.

One assertion was corrected during implementation: the first version required `always()` on every post-gate step, which failed against the *correct* workflow because `Open a tracking issue when the vulnix gate fails` deliberately runs on `failure()`. It now requires an explicit `if:`, which is the invariant that actually prevents this defect.

**Release note:** landed on `release/1.6.0` after `1.6.0-rc1` was cut, deliberately without an rc2 re-cut — `security-scan.yml` is devkit-only (not scaffolded to consumers, not in the image), so rc1's validation of the shipped artifact is unaffected.

