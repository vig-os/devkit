---
type: issue
state: closed
created: 2026-08-20T06:50:05Z
updated: 2026-08-20T07:22:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1548
comments: 1
labels: bug, priority:medium, area:ci, effort:small, semver:patch, security
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-20T12:22:20.933Z
---

# [Issue 1548]: [[BUG] Nightly security scan fails silently when a step before the vulnix gate fails](https://github.com/vig-os/devkit/issues/1548)

### Description

`security-scan.yml` opens a deduplicated tracking issue when the nightly scan
goes red (#965, #1237) — but the step is guarded on the **gate step's** outcome:

```yaml
# .github/workflows/security-scan.yml:235
if: ${{ failure() && steps.vulnix-gate.outcome == 'failure' }}
```

Any failure *before* `vulnix-gate` leaves `steps.vulnix-gate.outcome` empty
(the step never ran), so the guard is false and the run dies **silently** — a
red run in Actions and nothing else. Scheduled runs execute from the default
branch with no other signal, which is the exact reason #965 restored the issue
in the first place.

### Evidence

This morning's run
([32335643087](https://github.com/vig-os/devkit/actions/runs/32335643087),
2026-08-20 05:27 UTC) failed on **both** lanes at the *first* step, `Validate
.vulnixignore exception expirations` (expired fzf block, #1547). `Open a
tracking issue when the vulnix gate fails` shows as **skipped** in both jobs,
and no `security-scan` issue exists. The failure surfaced only because a human
went looking at the workflow list.

The blind window is every step ahead of the gate: the expiration validation, the
NVD cache restore, the closure build, the vulnix run itself, SBOM generation.
An expired register is the *most likely* of these — it is a scheduled, dated
event the grid deliberately creates (#1337).

### Expected Behavior

Any job failure in the nightly scan surfaces as a deduplicated tracking issue,
with the body distinguishing a **gate** failure (unexcepted HIGH/CRITICAL
findings) from a **pre-gate** failure (register expired, scan/infra crash) so
the issue is actionable without opening the run.

### Actual Behavior

Only a `vulnix-gate` failure opens an issue; everything upstream of it is
silent.

### Notes

- The dedup title is currently gate-specific ("unexcepted HIGH/CRITICAL vulnix
  findings"). A pre-gate failure needs either its own ref-distinct title or a
  reworded shared one — the two lanes must keep deduping independently (#1237).
- Kept out of the #1547 renewal PR to preserve the minimal diff: #1547 clears
  today's red, this one closes the reporting hole that hid it.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 20, 2026 at 07:22 AM_

Fixed on `dev` in #1550 (merge `fe593bbd`).

The guard is now `failure()` alone, so the whole job is in scope — register validation, NVD cache, closure build, the vulnix run, SBOM generation. Two dedup titles keep the classes independent per ref: a red gate keeps its exact existing title (issues already open under it still match), and a pre-gate failure files *run failed before the vulnix gate*, states that the closure went **unscanned, not clean**, and names the failing step from the run's own job records (`actions: read`).

Verified beyond YAML shape — the `run:` block was extracted and executed against a `gh` stub: the gate case reproduces the current title and body; the pre-gate case names the *dev* leg's failing step while the same payload carried a different failing step on the main leg; an already-open issue short-circuits before create.

Left out of scope deliberately: auto-closing the tracking issue on a later green run. Both classes are still closed by hand, as before.

Note the live check is tonight's 05:00 UTC `main` lane — it still carries the expired register (#1547 fixed only `dev`) but **not** this fix, so it will fail exactly as it did this morning, silently. The first real exercise of this path is whichever lane fails once 1.11.0 promotes.

