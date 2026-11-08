---
type: issue
state: open
created: 2026-10-27T08:54:29Z
updated: 2026-10-27T14:48:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1925
comments: 1
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-28T08:13:04.446Z
---

# [Issue 1925]: [#1908 S1: Runner selection core: `resolve-toolchain` and `ci.yml`](https://github.com/vig-os/devkit/issues/1925)

Implementation sub-issue **S1** of #1908, from the accepted [ADR-site-agnostic-projects](https://github.com/vig-os/devkit/blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (section *Implementation*; amended by #1923: every lane defaults to SMALL). The ADR is the design; this text is copied from it verbatim.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S4, S5 and S6 are independent. S7/S7b follow S1–S6, S8 gates release N, and S9 is release N+2. See the ADR's file-overlap table.

- *Scope:*
  - the §3 algorithm for the three classes, with the built-in lane defaults of
    §5 and no override key (that is S1b);
  - the inputs `runner-small`, `runner-large`, `runner-xlarge` and
    `legacy-resolve-runner`. All default to `''`, so a caller that S2 has not
    migrated yet keeps today's behaviour: its `runner-json` alias resolves
    from the legacy key or the default, and it is already fork-safe because
    the action evaluates the predicate;
  - the outputs `runners`, `runner-sources` and the deprecated `runner-json`
    alias;
  - the predicate evaluated in-action, and the malformed-variable `::error::`
    (needed for correctness). All other diagnostics are S1d;
  - the `ci.yml` wiring per §4;
  - the `.vig-os` template comments, replacing the site-specific example label
    with `<label>`.
- *Files:* `assets/workspace/.github/actions/resolve-toolchain/action.yml`,
  `assets/workspace/.github/workflows/ci.yml`, `assets/workspace/.vig-os`,
  `assets/workspace/.github/actionlint.yaml` (comment),
  `tests/test_ci_runner.py` (including scrubbing its site-specific label
  fixture), and the two tests that pin today's `ci.yml` wiring:
  `tests/test_scaffold_drift.py` (`test_scaffold_drift_honors_runner_override`)
  and `tests/test_workflow_ci_extension.py`
  (`test_extension_job_passes_the_resolved_toolchain_context`).
- *Shape-test rule* (`tests/test_ci_runner.py`). A `runs-on` value is one of
  three things:
  1. a **literal hosted label**;
  2. a **direct expression**, which must contain the §2 predicate;
  3. a **`fromJSON(...)` lane**, which may read only
     `needs.<resolver>.outputs.runners` or `needs.<resolver>.outputs.runner-json`
     (the resolver's job runs the action, so the action supplies the fork
     safety) or `inputs.runners` or `inputs.runner-json` of a reusable
     workflow whose every caller passes one of those outputs.

  At S1 the test is parametrized over `ci.yml` and `ci-extension.yml` only.
  `test_resolve_toolchain_runner_is_var_overridable` is split: `ci.yml`
  expects the new direct expression, and the other six resolvers keep
  `RESOLVE_RUNNER_EXPR` until S2. **S2 widens both** to every scaffolded
  workflow. That way S1 lands green while S2's workflows still carry the
  legacy expression.
- *Acceptance:*
  - executed-bash tests for each class and source: fork, variable,
    legacy-key, default;
  - variable wins over the key, per (a);
  - a malformed variable fails with an `::error::` naming it: a comma list,
    a JSON list (`["pool-l"]`), a label with surrounding or inner
    whitespace, and any character outside the label rule of §1;
  - a valid label with `. _ : / -` passes;
  - a whitespace-only variable is treated as unset;
  - no variables and no key gives `ubuntu-26.04` everywhere;
  - the shape test above;
  - a test that no scaffolded workflow declares `workflow_run` or
    `merge_group` (all workflows from S1 on: true today);
  - `ci.yml` lanes reference `runners` per §4;
  - a caller that passes none of the new inputs keeps today's `runner-json`.

Refs #1908
---

# [Comment #1]() by [gerchowl]()

_Posted on October 27, 2026 at 02:48 PM_

Data point from exo-pet/MPECT#313 / PR #314 (ksb ARC runners, 2026-10-27). With one `runner-json` for every lane, a project can't follow its host's rule ('light lanes on small, heavy test lanes on large'). Measured on ksb-exo-pet-small (2 CPU / 8 GiB): **Tests timed out at 20m24s**, against 10m40s on large; Lint took 9m53s on small with a cold toolchain. So MPECT needs Tests on large and the light lanes (Lint, Commit Messages, Devkit staleness, Scaffold Drift) on small. Today every lane sits on large, and the org's 2 large slots serialize PRs (one run queued for more than 1 h). Per-class routing from S1 is exactly what fixes this; please keep a per-lane override that leaves Tests on large.

